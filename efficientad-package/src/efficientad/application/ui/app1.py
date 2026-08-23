"""双 ROI EfficientAD 图形界面。

界面流程：选择一张原图 → 选择两个模型产物目录 → 选择两个 ROI 配置 →
执行检测 → 在原图和两个 ROI 卡片中展示热力图、loss、score 与判定。

模型通过目录直接选择，不依赖 ``my_product`` 或固定的 model/product 命名。
"""

from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from efficientad.application.imagepipeline import DualImagePipeline, DualROIConfig
from efficientad.application.imagepipeline.rendering import (
    render_dual_overlay,
    render_roi_overlay,
)

from .discovery import (
    discover_weight_dirs,
    inspect_weight_dir,
    load_threshold,
    resolve_weight_dir,
)

DEFAULT_THRESHOLDS = (0.2, 0.912657)
IMAGE_EXTENSIONS = "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"
AGGREGATION_OPTIONS = {
    "任一 ROI 异常": "any_anomaly",
    "两个 ROI 都异常": "all_anomaly",
    "最高相对阈值": "highest_relative_score",
}


def _package_root() -> Path:
    """定位独立包根目录，优先使用当前工作目录。"""

    this = Path(__file__).resolve()
    candidates = (Path.cwd(), this.parents[4])
    for candidate in candidates:
        if (candidate / "output").is_dir() or (candidate / "roi_configs").is_dir():
            return candidate
    return Path.cwd()


def _default_roi_path(root: Path, name: str) -> Path:
    candidates = (
        root / "roi_configs" / name,
        root.parent / "roi_configs" / name,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _to_rgb_image(bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


class EfficientADUI:
    """双 ROI 检测主窗口。"""

    def __init__(
        self,
        root: tk.Tk,
        *,
        source_dir: str | Path | None = None,
        image_path: str | None = None,
        model30: str | Path | None = None,
        model31: str | Path | None = None,
        roi30: str | Path | None = None,
        roi31: str | Path | None = None,
        threshold30: float | None = None,
        threshold31: float | None = None,
        device: str = "auto",
        heatmap_alpha: float = 0.45,
        aggregation_policy: str = "any_anomaly",
        # 保留旧构造参数，避免外部调用立即崩溃；新界面不再使用 product。
        model: str | None = None,
        product: str | None = None,
        threshold: float | None = None,
    ) -> None:
        del model, product, threshold
        self.root = root
        self.source_dir = Path(source_dir).expanduser().resolve() if source_dir else _package_root()
        self.device = device
        self.initial_heatmap_alpha = max(0.1, min(0.9, float(heatmap_alpha)))
        self.initial_aggregation_policy = aggregation_policy
        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._preview_refs: list[ImageTk.PhotoImage] = []
        self._roi_preview_refs: list[ImageTk.PhotoImage] = []

        self.root.title("EfficientAD · 双 ROI 缺陷检测")
        # 根据屏幕大小决定初始窗口尺寸，避免 1080p 屏幕被固定 900px 高度挤出可视区域。
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        window_w = min(1480, max(1080, screen_w - 80))
        window_h = min(900, max(720, screen_h - 140))
        self.root.geometry(f"{window_w}x{window_h}")
        self.root.minsize(960, 640)

        self._build_widgets()
        self._set_initial_values(
            image_path=image_path,
            model30=model30,
            model31=model31,
            roi30=roi30,
            roi31=roi31,
            threshold30=threshold30,
            threshold31=threshold31,
        )
        self.heatmap_alpha_var.set(self.initial_heatmap_alpha)
        self._on_alpha_changed(str(self.initial_heatmap_alpha))
        reverse_policies = {value: label for label, value in AGGREGATION_OPTIONS.items()}
        self.aggregation_var.set(reverse_policies.get(self.initial_aggregation_policy, "任一 ROI 异常"))
        self._scan_output_models()
        self.root.after(100, self._poll_queue)

    # ── 界面构建 ──────────────────────────────────────────────

    def _build_widgets(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        title = ttk.Label(main, text="EfficientAD 双 ROI 检测", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 10))

        input_frame = ttk.LabelFrame(main, text="输入图像", padding=8)
        input_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="原图:").grid(row=0, column=0, sticky="w")
        self.image_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.image_var).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(input_frame, text="选择图片", command=self._browse_image).grid(row=0, column=2)

        model_frame = ttk.LabelFrame(main, text="模型权重（直接选择 output 下的完整模型目录）", padding=8)
        model_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        model_frame.columnconfigure(1, weight=1)
        model_frame.columnconfigure(3, weight=1)
        model_frame.columnconfigure(5, weight=0)
        ttk.Label(model_frame, text="output 根目录:").grid(row=0, column=0, sticky="w")
        self.output_var = tk.StringVar()
        ttk.Entry(model_frame, textvariable=self.output_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=6
        )
        ttk.Button(model_frame, text="选择目录", command=self._browse_output).grid(row=0, column=4)
        ttk.Button(model_frame, text="扫描模型", command=self._scan_output_models).grid(
            row=0, column=5, padx=(6, 0)
        )

        self.model_vars = [tk.StringVar(), tk.StringVar()]
        self.model_combos: list[ttk.Combobox] = []
        self.model_status_vars = [tk.StringVar(value="未选择") for _ in range(2)]
        self.model_status_labels: list[ttk.Label] = []
        for index, name in enumerate(("ROI-30 权重:", "ROI-31 权重:"), start=1):
            ttk.Label(model_frame, text=name).grid(row=index, column=0, sticky="w", pady=(6, 0))
            combo = ttk.Combobox(model_frame, textvariable=self.model_vars[index - 1], state="readonly")
            combo.grid(row=index, column=1, columnspan=3, sticky="ew", padx=6, pady=(6, 0))
            combo.bind(
                "<<ComboboxSelected>>",
                lambda _event, slot=index - 1: self._on_model_selected(slot),
            )
            self.model_combos.append(combo)
            ttk.Button(
                model_frame,
                text="浏览目录",
                command=lambda slot=index - 1: self._browse_model(slot),
            ).grid(row=index, column=4, padx=(0, 6), pady=(6, 0))
            status_label = ttk.Label(
                model_frame,
                textvariable=self.model_status_vars[index - 1],
                foreground="#777777",
            )
            status_label.grid(row=index, column=5, sticky="w", pady=(6, 0))
            self.model_status_labels.append(status_label)

        roi_frame = ttk.LabelFrame(main, text="ROI 配置与阈值", padding=8)
        roi_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        roi_frame.columnconfigure(1, weight=1)
        roi_frame.columnconfigure(4, weight=1)
        self.roi_vars = [tk.StringVar(), tk.StringVar()]
        self.threshold_vars = [tk.StringVar(), tk.StringVar()]
        for index, name in enumerate(("ROI-30:", "ROI-31:")):
            row = index
            ttk.Label(roi_frame, text=name).grid(row=row, column=0, sticky="w", pady=(0 if row == 0 else 6, 0))
            ttk.Entry(roi_frame, textvariable=self.roi_vars[index]).grid(
                row=row, column=1, sticky="ew", padx=6, pady=(0 if row == 0 else 6, 0)
            )
            ttk.Button(
                roi_frame,
                text="选择 JSON",
                command=lambda slot=index: self._browse_roi(slot),
            ).grid(row=row, column=2, pady=(0 if row == 0 else 6, 0))
            ttk.Label(roi_frame, text="阈值:").grid(row=row, column=3, sticky="e", padx=(24, 0))
            ttk.Entry(roi_frame, textvariable=self.threshold_vars[index], width=12).grid(
                row=row, column=4, sticky="w", padx=6, pady=(0 if row == 0 else 6, 0)
            )

        action_frame = ttk.Frame(main)
        action_frame.grid(row=4, column=0, sticky="nsew", pady=(2, 0))
        action_frame.columnconfigure(0, weight=1)
        action_frame.rowconfigure(1, weight=1)
        top_action = ttk.Frame(action_frame)
        top_action.grid(row=0, column=0, sticky="ew")
        self.device_var = tk.StringVar(value=self.device)
        self.heatmap_alpha_var = tk.DoubleVar(value=0.45)
        self.alpha_text_var = tk.StringVar(value="45%")
        self.aggregation_var = tk.StringVar(value="任一 ROI 异常")
        ttk.Label(top_action, text="设备:").pack(side=tk.LEFT)
        ttk.Combobox(
            top_action,
            textvariable=self.device_var,
            state="readonly",
            values=("auto", "cpu", "cuda"),
            width=8,
        ).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(top_action, text="热力图:").pack(side=tk.LEFT)
        ttk.Scale(
            top_action,
            from_=0.1,
            to=0.9,
            variable=self.heatmap_alpha_var,
            command=self._on_alpha_changed,
            length=110,
        ).pack(side=tk.LEFT, padx=(6, 3))
        ttk.Label(top_action, textvariable=self.alpha_text_var, width=4).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Label(top_action, text="整体判定:").pack(side=tk.LEFT)
        ttk.Combobox(
            top_action,
            textvariable=self.aggregation_var,
            state="readonly",
            values=tuple(AGGREGATION_OPTIONS),
            width=16,
        ).pack(side=tk.LEFT, padx=(6, 16))
        self.detect_button = ttk.Button(top_action, text="开始双 ROI 检测", command=self._run_detection)
        self.detect_button.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="请选择原图、两个模型目录和两个 ROI 配置")
        ttk.Label(top_action, textvariable=self.status_var, foreground="gray").pack(
            side=tk.RIGHT, padx=6
        )

        result_frame = ttk.LabelFrame(action_frame, text="检测结果", padding=8)
        result_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.result_frame = result_frame
        result_frame.columnconfigure(0, weight=1)
        result_frame.columnconfigure(1, weight=0)
        result_frame.rowconfigure(0, weight=1)

        self.full_preview = ttk.Label(result_frame, text="检测后显示原图、ROI 框和热力图", anchor="center")
        self.full_preview.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        side = ttk.Frame(result_frame)
        side.grid(row=0, column=1, sticky="nsew")
        side.configure(width=380)
        side.grid_propagate(False)
        side.columnconfigure(0, weight=1)
        self.overall_var = tk.StringVar(value="整体判定: -")
        self.overall_score_var = tk.StringVar(value="最高 score: -")
        self.overall_ratio_var = tk.StringVar(value="最高相对阈值: -")
        ttk.Label(side, textvariable=self.overall_var, font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 2)
        )
        ttk.Label(side, textvariable=self.overall_score_var, font=("Consolas", 11)).grid(
            row=1, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Label(side, textvariable=self.overall_ratio_var, font=("Consolas", 11)).grid(
            row=2, column=0, sticky="w", pady=(0, 8)
        )
        self.roi_stat_vars = [tk.StringVar(value=f"ROI-{30 + index}: -") for index in range(2)]
        self.roi_previews: list[ttk.Label] = []
        for index in range(2):
            card = ttk.LabelFrame(side, text=f"ROI-{30 + index}", padding=6)
            card.grid(row=3 + index * 2, column=0, sticky="ew", pady=(0, 6))
            ttk.Label(card, textvariable=self.roi_stat_vars[index], justify=tk.LEFT).pack(anchor="w")
            preview = ttk.Label(card, text="热力图预览", anchor="center")
            preview.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            self.roi_previews.append(preview)

    # ── 初始化与选择 ──────────────────────────────────────────

    def _set_initial_values(
        self,
        *,
        image_path: str | None,
        model30: str | Path | None,
        model31: str | Path | None,
        roi30: str | Path | None,
        roi31: str | Path | None,
        threshold30: float | None,
        threshold31: float | None,
    ) -> None:
        self.output_var.set(str(self.source_dir / "output"))
        self.image_var.set(image_path or "")
        self.model_vars[0].set(str(model30) if model30 else "")
        self.model_vars[1].set(str(model31) if model31 else "")
        self.roi_vars[0].set(str(roi30 or _default_roi_path(self.source_dir, "roi30.json")))
        self.roi_vars[1].set(str(roi31 or _default_roi_path(self.source_dir, "roi31.json")))
        self.threshold_vars[0].set("" if threshold30 is None else f"{threshold30:g}")
        self.threshold_vars[1].set("" if threshold31 is None else f"{threshold31:g}")

    def _on_alpha_changed(self, value: str) -> None:
        self.alpha_text_var.set(f"{float(value):.0%}")

    def _refresh_model_status(self, slot: int) -> None:
        path = self.model_vars[slot].get().strip()
        if not path:
            self.model_status_vars[slot].set("未选择")
            return
        status = inspect_weight_dir(path)
        labels = (
            ("student", "Student"),
            ("autoencoder", "AE"),
            ("normalization", "Norm"),
        )
        text = "  ".join(
            f"{'✓' if status[key] else '✗'} {label}" for key, label in labels
        )
        self.model_status_vars[slot].set(text)

    def _scan_output_models(self) -> None:
        try:
            weights = discover_weight_dirs(self.output_var.get().strip())
        except Exception as error:  # noqa: BLE001 - UI 统一展示
            self.status_var.set(f"扫描失败: {error}")
            return
        labels = [str(item.model_dir) for item in weights]
        for combo in self.model_combos:
            combo["values"] = labels
        if not labels:
            self.status_var.set("未发现完整模型目录（需要 student、autoencoder、norm_params）")
            return

        self._select_default_model(0, weights, ("roi30", "\\30\\", "/30/"))
        self._select_default_model(1, weights, ("roi31", "\\31\\", "/31/"))
        self._refresh_model_status(0)
        self._refresh_model_status(1)
        self.status_var.set(f"已发现 {len(labels)} 个可用模型目录")

    def _select_default_model(self, slot: int, weights, tokens: tuple[str, ...]) -> None:
        if self.model_vars[slot].get().strip():
            return
        for item in weights:
            lowered = str(item.model_dir).lower().replace("\\", "/")
            if any(token.replace("\\", "/") in lowered for token in tokens):
                self._set_model(slot, item.model_dir, item.threshold)
                return
        index = min(slot, len(weights) - 1)
        self._set_model(slot, weights[index].model_dir, weights[index].threshold)

    def _set_model(self, slot: int, path: str | Path, threshold: float | None = None) -> None:
        self.model_vars[slot].set(str(path))
        self._refresh_model_status(slot)
        if threshold is not None and not self.threshold_vars[slot].get().strip():
            self.threshold_vars[slot].set(f"{threshold:g}")
        elif not self.threshold_vars[slot].get().strip():
            self.threshold_vars[slot].set(f"{DEFAULT_THRESHOLDS[slot]:g}")

    def _on_model_selected(self, slot: int) -> None:
        threshold = load_threshold(self.model_vars[slot].get())
        self._set_model(slot, self.model_vars[slot].get(), threshold)

    def _browse_image(self) -> None:
        path = filedialog.askopenfilename(
            title="选择原图",
            filetypes=[("图像", IMAGE_EXTENSIONS), ("所有文件", "*.*")],
        )
        if path:
            self.image_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="选择 output 根目录")
        if path:
            self.output_var.set(path)
            self._scan_output_models()

    def _browse_model(self, slot: int) -> None:
        path = filedialog.askdirectory(title=f"选择 ROI-{30 + slot} 模型产物目录")
        if path:
            self._set_model(slot, path, load_threshold(path))

    def _browse_roi(self, slot: int) -> None:
        path = filedialog.askopenfilename(
            title=f"选择 ROI-{30 + slot} 配置",
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")],
        )
        if path:
            self.roi_vars[slot].set(path)

    # ── 检测与结果 ─────────────────────────────────────────────

    def _run_detection(self) -> None:
        if self._busy:
            return
        image_path = self.image_var.get().strip()
        if not image_path or not Path(image_path).is_file():
            messagebox.showerror("错误", "请选择有效的原图文件")
            return
        try:
            thresholds = tuple(float(value.get()) for value in self.threshold_vars)
        except ValueError:
            messagebox.showerror("错误", "两个阈值都必须是数字")
            return
        if any(not value.get().strip() for value in self.model_vars):
            messagebox.showerror("错误", "请选择两个模型产物目录")
            return
        if any(not value.get().strip() or not Path(value.get()).is_file() for value in self.roi_vars):
            messagebox.showerror("错误", "请选择两个 ROI JSON 配置文件")
            return

        self._busy = True
        self.detect_button.state(["disabled"])
        self.status_var.set("正在加载两个模型并检测 ROI-30 / ROI-31 ...")
        device = self.device_var.get()
        alpha = float(self.heatmap_alpha_var.get())
        policy = AGGREGATION_OPTIONS[self.aggregation_var.get()]
        thread = threading.Thread(
            target=self._worker,
            args=(
                image_path,
                tuple(self.model_vars[index].get() for index in range(2)),
                tuple(self.roi_vars[index].get() for index in range(2)),
                thresholds,
                device,
                alpha,
                policy,
            ),
            daemon=True,
        )
        thread.start()

    def _worker(self, image_path: str, model_dirs, roi_paths, thresholds, device, alpha, policy) -> None:
        try:
            configs = tuple(
                DualROIConfig.from_files(
                    name=f"ROI-{30 + index}",
                    model_dir=resolve_weight_dir(model_dirs[index]),
                    roi_config=roi_paths[index],
                    threshold=thresholds[index],
                )
                for index in range(2)
            )
            pipeline = DualImagePipeline(configs, device=device)
            result = pipeline.process(image_path)
            annotated = render_dual_overlay(
                result.image,
                result.rois,
                alpha=alpha,
                overall_policy=policy,
            )
            roi_images = tuple(
                render_roi_overlay(
                    item.roi_image,
                    item.heatmap,
                    label=f"{item.name} {'ANOMALY' if item.is_anomaly else 'NORMAL'}",
                    color=(0, 0, 255) if item.is_anomaly else (0, 200, 0),
                    alpha=alpha,
                )
                for item in result.rois
            )
            self._queue.put(("ok", result, annotated, roi_images, policy))
        except Exception as error:  # noqa: BLE001 - UI 统一展示
            self._queue.put(("error", f"{type(error).__name__}: {error}"))

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._queue.get_nowait()
                self._busy = False
                self.detect_button.state(["!disabled"])
                if item[0] == "ok":
                    _, result, annotated, roi_images, policy = item
                    self._show_result(result, annotated, roi_images, policy)
                else:
                    self.status_var.set("检测失败")
                    messagebox.showerror("检测失败", item[1])
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _show_result(self, result, annotated: np.ndarray, roi_images, policy: str) -> None:
        verdict_bool, relative_score = result.aggregate(policy)
        verdict = "ANOMALY" if verdict_bool else "NORMAL"
        self.overall_var.set(f"整体判定: {verdict}")
        self.overall_score_var.set(f"最高 score: {result.score:.6f}")
        self.overall_ratio_var.set(f"最高相对阈值: {relative_score:.3f}x")
        # 先让 Tk 完成布局，再按照“当前真正可用的空间”计算图片上限。
        # 这样窗口在 1080p / 2K / 4K 或用户手动缩放时都不会被大图撑爆。
        self.root.update_idletasks()
        full_width = max(320, self.full_preview.winfo_width() - 16)
        full_height = max(220, self.full_preview.winfo_height() - 16)

        # 右侧还要留空间给整体判定和每个 ROI 的文字信息，因此 ROI 小图
        # 不直接使用整列高度，而是按结果区高度动态分配。
        result_height = max(300, self.result_frame.winfo_height())
        roi_height = max(90, min(180, (result_height - 230) // 2))
        roi_width = max(180, min(320, self.roi_previews[0].winfo_width() - 12))

        for index, item in enumerate(result.rois):
            self.roi_stat_vars[index].set(
                f"{item.name}: {'ANOMALY' if item.is_anomaly else 'NORMAL'}\n"
                f"score={item.score:.6f}  threshold={item.threshold:.6f}\n"
                f"loss={item.loss:.6f}\n"
                f"model={item.model_dir.name}"
            )
            self._show_preview(
                self.roi_previews[index],
                roi_images[index],
                max_width=roi_width,
                max_height=roi_height,
                slot=index,
                roi=True,
            )

        self._show_preview(
            self.full_preview,
            annotated,
            max_width=full_width,
            max_height=full_height,
            slot=0,
            roi=False,
        )
        self.status_var.set("检测完成：两个 ROI 均已处理")

    def _show_preview(
        self,
        label: ttk.Label,
        bgr: np.ndarray,
        *,
        max_width: int,
        max_height: int,
        slot: int,
        roi: bool,
    ) -> None:
        image = _to_rgb_image(bgr)
        width, height = image.size
        scale = min(max_width / width, max_height / height, 1.0)
        if scale < 1.0:
            image = image.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.Resampling.LANCZOS,
            )
        photo = ImageTk.PhotoImage(image)
        label.configure(image=photo, text="")
        refs = self._roi_preview_refs if roi else self._preview_refs
        while len(refs) <= slot:
            refs.append(photo)
        refs[slot] = photo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="efficientad-ui", description=__doc__)
    parser.add_argument("--image", default=None, help="初始原图路径")
    parser.add_argument("--model30", default=None, help="ROI-30 模型产物目录")
    parser.add_argument("--model31", default=None, help="ROI-31 模型产物目录")
    parser.add_argument("--roi30", default=None, help="ROI-30 JSON 配置")
    parser.add_argument("--roi31", default=None, help="ROI-31 JSON 配置")
    parser.add_argument("--threshold30", type=float, default=None)
    parser.add_argument("--threshold31", type=float, default=None)
    parser.add_argument("--heatmap-alpha", type=float, default=0.45, help="热力图透明度 0.1~0.9")
    parser.add_argument(
        "--aggregation",
        choices=tuple(AGGREGATION_OPTIONS.values()),
        default="any_anomaly",
        help="整体判定策略",
    )
    parser.add_argument("--source-dir", default=None, help="efficientad-package 根目录")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = tk.Tk()
    EfficientADUI(
        root,
        source_dir=args.source_dir,
        image_path=args.image,
        model30=args.model30,
        model31=args.model31,
        roi30=args.roi30,
        roi31=args.roi31,
        threshold30=args.threshold30,
        threshold31=args.threshold31,
        device=args.device,
        heatmap_alpha=args.heatmap_alpha,
        aggregation_policy=args.aggregation,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
