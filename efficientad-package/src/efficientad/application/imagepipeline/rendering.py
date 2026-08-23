"""纯内存渲染：图像 + 热力图 → 叠加图。不写文件（保存归 CLI/显式 writer）。"""

from __future__ import annotations

import cv2
import numpy as np

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .dual import DualROIResult, DualPipelineResult

HEATMAP_ALPHA = 0.45


def render_overlay(
    image_bgr: np.ndarray,
    heatmap: np.ndarray,
    *,
    corners: np.ndarray | None = None,
    text: str | None = None,
    box_color: tuple[int, int, int] = (0, 0, 255),
    alpha: float = HEATMAP_ALPHA,
) -> np.ndarray:
    """把热力图（尺寸与 ROI 裁剪图一致）伪彩叠加到图像上，返回渲染结果。

    若提供 ``corners``（原图坐标系四角）且热力图尺寸小于图像，则在
    四角区域内叠加；否则按热力图尺寸等比覆盖。
    """
    output = image_bgr.copy()
    if corners is not None and heatmap.shape[:2] != image_bgr.shape[:2]:
        pts = np.round(corners).astype(int)
        x0, y0 = pts.min(axis=0)
        x1, y1 = pts.max(axis=0)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, image_bgr.shape[1]), min(y1, image_bgr.shape[0])
        if x1 > x0 and y1 > y0:
            h, w = y1 - y0, x1 - x0
            resized = cv2.resize(heatmap, (w, h), interpolation=cv2.INTER_LINEAR)
            _blend_heatmap(output, resized, y0, x0, alpha=alpha)
    elif heatmap.shape[:2] == image_bgr.shape[:2]:
        _blend_heatmap(output, heatmap, 0, 0, alpha=alpha)

    if corners is not None:
        pts = np.round(corners).astype(np.int32)
        cv2.polylines(output, [pts], isClosed=True, color=box_color, thickness=2)
    if text:
        org = (int(corners[0][0]), max(int(corners[0][1]) - 10, 20)) if corners is not None else (16, 32)
        cv2.putText(output, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return output


def _blend_heatmap(
    output: np.ndarray,
    heatmap: np.ndarray,
    top: int,
    left: int,
    *,
    alpha: float = HEATMAP_ALPHA,
) -> None:
    normalized = np.clip(heatmap, 0.0, 1.0)
    color = cv2.applyColorMap((normalized * 255).astype(np.uint8), cv2.COLORMAP_JET)
    region = output[top : top + heatmap.shape[0], left : left + heatmap.shape[1]]
    output[top : top + heatmap.shape[0], left : left + heatmap.shape[1]] = cv2.addWeighted(
        region, 1 - alpha, color, alpha, 0
    )


def render_dual_overlay(
    image_bgr: np.ndarray,
    results: Iterable["DualROIResult"],
    *,
    alpha: float = HEATMAP_ALPHA,
    overall_policy: str = "any_anomaly",
) -> np.ndarray:
    """在原图上叠加多个 ROI 热力图、边框、标签和整体判定。"""

    output = image_bgr.copy()
    results = tuple(results)
    for result in results:
        x, y, width, height = result.roi
        if width <= 0 or height <= 0:
            continue
        if x < 0 or y < 0 or x + width > output.shape[1] or y + height > output.shape[0]:
            continue
        resized = cv2.resize(result.heatmap, (width, height), interpolation=cv2.INTER_LINEAR)
        _blend_heatmap(output, resized, y, x, alpha=alpha)
        color = (0, 0, 255) if result.is_anomaly else (0, 200, 0)
        cv2.rectangle(output, (x, y), (x + width, y + height), color, 3)

        label = (
            f"{result.name} {'ANOMALY' if result.is_anomaly else 'NORMAL'} "
            f"score={result.score:.4f} thr={result.threshold:.4f}"
        )
        label_y = y - 8 if y > 32 else min(y + height + 26, output.shape[0] - 8)
        _draw_label(output, label, (x, label_y), color)

    verdict = _aggregate_verdict(results, overall_policy)
    verdict = "ANOMALY" if verdict else "NORMAL"
    summary = "VERDICT " + verdict
    if results:
        summary += " | " + " | ".join(
            f"{result.name} {result.score:.4f}" for result in results
        )
    overlay = output.copy()
    cv2.rectangle(overlay, (0, 0), (output.shape[1], 50), (25, 25, 25), -1)
    output = cv2.addWeighted(overlay, 0.82, output, 0.18, 0)
    cv2.putText(
        output,
        summary,
        (16, 33),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.78,
        (0, 0, 255) if verdict == "ANOMALY" else (0, 220, 0),
        2,
        cv2.LINE_AA,
    )
    return output


def render_roi_overlay(
    roi_image_bgr: np.ndarray,
    heatmap: np.ndarray,
    *,
    label: str,
    color: tuple[int, int, int],
    alpha: float = HEATMAP_ALPHA,
) -> np.ndarray:
    """渲染单个 ROI 裁剪图及其热力图，供 UI 结果卡片展示。"""

    output = roi_image_bgr.copy()
    resized = cv2.resize(heatmap, (output.shape[1], output.shape[0]), interpolation=cv2.INTER_LINEAR)
    _blend_heatmap(output, resized, 0, 0, alpha=alpha)
    cv2.rectangle(output, (0, 0), (output.shape[1] - 1, output.shape[0] - 1), color, 3)
    _draw_label(output, label, (8, 24), color)
    return output


def _draw_label(
    image: np.ndarray,
    text: str,
    origin: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    x, baseline_y = origin
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.58
    thickness = 2
    (text_width, text_height), _ = cv2.getTextSize(text, font, scale, thickness)
    top = max(0, baseline_y - text_height - 8)
    left = max(0, x - 4)
    right = min(image.shape[1], x + text_width + 8)
    bottom = min(image.shape[0], baseline_y + 5)
    cv2.rectangle(image, (left, top), (right, bottom), color, -1)
    cv2.putText(image, text, (x, min(image.shape[0] - 4, baseline_y)), font, scale,
                (255, 255, 255), thickness, cv2.LINE_AA)


def _aggregate_verdict(results: tuple["DualROIResult", ...], policy: str) -> bool:
    if policy == "all_anomaly":
        return bool(results) and all(result.is_anomaly for result in results)
    if policy == "highest_relative_score":
        ratios = [
            result.score / result.threshold if result.threshold > 0 else float("inf")
            for result in results
        ]
        return bool(ratios) and max(ratios) >= 1.0
    return any(result.is_anomaly for result in results)


__all__ = ["render_dual_overlay", "render_overlay", "render_roi_overlay"]
