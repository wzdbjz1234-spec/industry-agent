"""ORB 特征匹配 ROI 处理器（原图存在偏移的场景）。

迁移自 ``pipeline.py::find_roi`` 与 ``roi_tool.py::crop_roi``（消除重复实现）。
模板目录约定：``templates/<name>/template.png`` + ``roi.json``。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .config import load_roi_config
from .fixed import apply_masks
from .processor import ROIConfigError, ROIMatchError
from .types import ROICropResult

ORB_FEATURES = 5000
RATIO_THRESH = 0.75
MIN_GOOD_MATCHES = 10
RANSAC_THRESH = 5.0

_orb = cv2.ORB_create(nfeatures=ORB_FEATURES)
_bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)


def _orb_homography(tpl_gray: np.ndarray, img_gray: np.ndarray) -> np.ndarray | None:
    """ORB 特征匹配 + RANSAC 单应矩阵；失败返回 None。"""
    kp1, des1 = _orb.detectAndCompute(tpl_gray, None)
    kp2, des2 = _orb.detectAndCompute(img_gray, None)
    if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
        return None
    matches = _bf.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < RATIO_THRESH * n.distance]
    if len(good) < MIN_GOOD_MATCHES:
        return None
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, _mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, RANSAC_THRESH)
    return H


def _default_templates_dir() -> Path:
    """默认模板目录：当前工作目录下的 templates/，或开发布局的仓库根 templates/。

    独立安装后建议显式传 ``templates_dir``。
    """
    candidates = [
        Path.cwd() / "templates",
        Path(__file__).resolve().parents[3] / "templates",  # 独立包根
        Path(__file__).resolve().parents[4] / "templates",  # 仓库根(开发布局)
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise ROIConfigError(
        "未指定 templates_dir，且默认位置不存在：" + ", ".join(str(c) for c in candidates)
    )


class ORBROIProcessor:
    """基于模板的 ORB 匹配 ROI：透视矫正裁剪 + 掩膜。"""

    def __init__(
        self,
        template_name: str,
        *,
        templates_dir: str | Path | None = None,
    ) -> None:
        base = (
            Path(templates_dir)
            if templates_dir is not None
            else _default_templates_dir()
        )
        tpl_dir = base / template_name
        template_img = cv2.imread(str(tpl_dir / "template.png"))
        if template_img is None:
            raise ROIConfigError(f"模板不存在: {tpl_dir / 'template.png'}")
        try:
            roi, masks = load_roi_config(tpl_dir / "roi.json")
        except (FileNotFoundError, KeyError) as error:
            raise ROIConfigError(f"ROI 配置非法: {tpl_dir / 'roi.json'} ({error})") from error

        self.template_name = template_name
        self.template_img = template_img
        self.template_gray = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
        self.roi = roi
        self.masks = tuple(tuple(map(int, mask)) for mask in masks)

    def crop(self, image: np.ndarray) -> ROICropResult:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"输入必须是 (H, W, 3) BGR 数组, 实际 {image.shape}")
        rx, ry, rw, rh = self.roi

        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        H = _orb_homography(self.template_gray, img_gray)
        if H is None:
            raise ROIMatchError(f"ORB 特征匹配失败 (模板 {self.template_name})")

        src_corners = np.float32(
            [[rx, ry], [rx + rw, ry], [rx + rw, ry + rh], [rx, ry + rh]]
        ).reshape(-1, 1, 2)
        dst_corners = cv2.perspectiveTransform(src_corners, H).reshape(4, 2)

        h_img, w_img = image.shape[:2]
        for pt in dst_corners:
            if pt[0] < 0 or pt[0] >= w_img or pt[1] < 0 or pt[1] >= h_img:
                raise ROIMatchError("映射后的 ROI 超出图像边界")

        out_w, out_h = int(rw), int(rh)
        dst_rect = np.float32(
            [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]]
        ).reshape(-1, 1, 2)
        M = cv2.getPerspectiveTransform(dst_corners.astype(np.float32).reshape(-1, 1, 2), dst_rect)
        warped = cv2.warpPerspective(image, M, (out_w, out_h))
        warped = apply_masks(warped, self.masks)

        x0, y0 = dst_corners.min(axis=0).astype(int)
        x1, y1 = dst_corners.max(axis=0).astype(int)
        return ROICropResult(
            image=warped,
            corners=dst_corners.astype(np.float32),
            rect=(x0, y0, x1 - x0, y1 - y0),
            masks=self.masks,
        )


__all__ = ["ORBROIProcessor"]
