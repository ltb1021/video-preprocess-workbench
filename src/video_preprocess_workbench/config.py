from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_EXTENSIONS = [".mp4", ".avi", ".mov", ".mkv", ".MP4", ".AVI", ".MOV", ".MKV"]


def _path_str(value: str, base_dir: Path) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def _normalize_extensions(values: list[str] | tuple[str, ...] | None) -> list[str]:
    items = values or DEFAULT_EXTENSIONS
    normalized = []
    for item in items:
        text = item.strip()
        if not text:
            continue
        normalized.append(text if text.startswith(".") else f".{text}")
    return normalized or DEFAULT_EXTENSIONS.copy()


@dataclass
class InputConfig:
    path: str = "../input_videos"
    mode: str = "dir"
    scan_depth: int | None = 0
    extensions: list[str] = field(default_factory=lambda: DEFAULT_EXTENSIONS.copy())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InputConfig":
        return cls(
            path=str(data.get("path", "../input_videos")),
            mode=str(data.get("mode", "dir")).lower(),
            scan_depth=data.get("scan_depth", 0),
            extensions=_normalize_extensions(data.get("extensions")),
        )


@dataclass
class OutputConfig:
    base_dir: str = "../artifacts/runs"
    run_name: str = "auto"
    output_ext: str = "mp4"
    preserve_subdirs: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutputConfig":
        return cls(
            base_dir=str(data.get("base_dir", "../artifacts/runs")),
            run_name=str(data.get("run_name", "auto")),
            output_ext=str(data.get("output_ext", "mp4")).lower().lstrip("."),
            preserve_subdirs=bool(data.get("preserve_subdirs", True)),
        )


@dataclass
class TransformConfig:
    resize_mode: str = "fit_pad"
    resize_width: int = 1280
    resize_height: int = 720
    crop_top: int = 0
    crop_bottom: int = 0
    crop_left: int = 0
    crop_right: int = 0
    target_fps: float = 10.0
    fps_mode: str = "downsample_only"
    preserve_duration: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransformConfig":
        return cls(
            resize_mode=str(data.get("resize_mode", "fit_pad")).lower(),
            resize_width=int(data.get("resize_width", 1280)),
            resize_height=int(data.get("resize_height", 720)),
            crop_top=int(data.get("crop_top", 0)),
            crop_bottom=int(data.get("crop_bottom", 0)),
            crop_left=int(data.get("crop_left", 0)),
            crop_right=int(data.get("crop_right", 0)),
            target_fps=float(data.get("target_fps", 10.0)),
            fps_mode=str(data.get("fps_mode", "downsample_only")).lower(),
            preserve_duration=bool(data.get("preserve_duration", True)),
        )


@dataclass
class RoiConfig:
    enabled: bool = False
    space: str = "normalized"
    boxes: list[dict[str, float]] = field(default_factory=list)
    blur_kernel: list[int] = field(default_factory=lambda: [151, 151])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoiConfig":
        boxes = data.get("boxes", []) or []
        normalized_boxes = []
        for box in boxes:
            normalized_boxes.append(
                {
                    "x": float(box.get("x", 0.0)),
                    "y": float(box.get("y", 0.0)),
                    "w": float(box.get("w", 0.0)),
                    "h": float(box.get("h", 0.0)),
                }
            )
        kernel = [int(v) for v in data.get("blur_kernel", [151, 151])]
        if len(kernel) != 2:
            kernel = [151, 151]
        return cls(
            enabled=bool(data.get("enabled", False)),
            space=str(data.get("space", "normalized")).lower(),
            boxes=normalized_boxes,
            blur_kernel=kernel,
        )


@dataclass
class PreviewConfig:
    enabled: bool = True
    video_index: int = 0
    debug_frame_index: int = 0
    grid_interval: int = 50

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreviewConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            video_index=int(data.get("video_index", 0)),
            debug_frame_index=int(data.get("debug_frame_index", 0)),
            grid_interval=int(data.get("grid_interval", 50)),
        )


@dataclass
class RunConfig:
    continue_on_error: bool = True
    log_every: int = 50

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunConfig":
        return cls(
            continue_on_error=bool(data.get("continue_on_error", True)),
            log_every=int(data.get("log_every", 50)),
        )


@dataclass
class SegmentConfig:
    start_sec: float = 290.0
    end_sec: float = 350.0
    preserve_source_fps: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SegmentConfig":
        return cls(
            start_sec=float(data.get("start_sec", 290.0)),
            end_sec=float(data.get("end_sec", 350.0)),
            preserve_source_fps=bool(data.get("preserve_source_fps", True)),
        )


@dataclass
class AppConfig:
    input: InputConfig = field(default_factory=InputConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    transform: TransformConfig = field(default_factory=TransformConfig)
    roi: RoiConfig = field(default_factory=RoiConfig)
    preview: PreviewConfig = field(default_factory=PreviewConfig)
    run: RunConfig = field(default_factory=RunConfig)
    segment: SegmentConfig = field(default_factory=SegmentConfig)
    config_path: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: str = "") -> "AppConfig":
        return cls(
            input=InputConfig.from_dict(data.get("input", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
            transform=TransformConfig.from_dict(data.get("transform", {})),
            roi=RoiConfig.from_dict(data.get("roi", {})),
            preview=PreviewConfig.from_dict(data.get("preview", {})),
            run=RunConfig.from_dict(data.get("run", {})),
            segment=SegmentConfig.from_dict(data.get("segment", {})),
            config_path=config_path,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("config_path", None)
        return data

    def resolved(self, base_dir: Path | None = None) -> "AppConfig":
        anchor = base_dir or (Path(self.config_path).resolve().parent if self.config_path else Path.cwd())
        clone = AppConfig.from_dict(self.to_dict(), config_path=self.config_path)
        clone.input.path = _path_str(clone.input.path, anchor)
        clone.output.base_dir = _path_str(clone.output.base_dir, anchor)
        return clone


def load_config(path: str | Path) -> AppConfig:
    cfg_path = Path(path).expanduser().resolve()
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return AppConfig.from_dict(data, config_path=str(cfg_path)).resolved(cfg_path.parent)


def create_example_config(destination: str | Path) -> Path:
    dst = Path(destination).expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    example = AppConfig()
    dst.write_text(json.dumps(example.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dst
