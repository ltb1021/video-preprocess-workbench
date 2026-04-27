from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import AppConfig


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def even_positive(value: int) -> int:
    value = max(1, int(value))
    return value if value % 2 == 1 else value + 1


def fourcc_for_ext(ext: str) -> int:
    key = ext.lower().lstrip(".")
    if key == "avi":
        return cv2.VideoWriter_fourcc(*"XVID")
    return cv2.VideoWriter_fourcc(*"mp4v")


def apply_overrides(
    cfg: AppConfig,
    input_path: str | None = None,
    output_dir: str | None = None,
    scan_depth: int | None | object = ...,
) -> AppConfig:
    updated = AppConfig.from_dict(cfg.to_dict(), config_path=cfg.config_path).resolved()
    if input_path:
        updated.input.path = str(Path(input_path).expanduser().resolve())
        updated.input.mode = "file" if Path(updated.input.path).is_file() else "dir"
    if output_dir:
        updated.output.base_dir = str(Path(output_dir).expanduser().resolve())
    if scan_depth is not ...:
        updated.input.scan_depth = scan_depth
    return updated


def resolve_run_dir(cfg: AppConfig) -> Path:
    base = Path(cfg.output.base_dir)
    run_name = cfg.output.run_name
    if run_name.lower() == "auto":
        run_name = f"run_{timestamp()}"
    return base / run_name


def _iter_video_files(root: Path, scan_depth: int | None, extensions: set[str]) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"입력 경로가 없습니다: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"폴더 모드인데 디렉터리가 아닙니다: {root}")

    limit = None if scan_depth is None or scan_depth < 0 else int(scan_depth)
    collected: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)
        if limit is not None and depth > limit:
            dirnames[:] = []
            continue
        if limit is not None and depth >= limit:
            dirnames[:] = []
        for name in sorted(filenames):
            path = current / name
            if path.suffix in extensions:
                collected.append(path)
    return sorted(collected)


def collect_video_paths(cfg: AppConfig) -> tuple[list[Path], Path]:
    source = Path(cfg.input.path)
    extensions = set(cfg.input.extensions)
    if cfg.input.mode == "file":
        if not source.exists():
            raise FileNotFoundError(f"입력 파일이 없습니다: {source}")
        return [source], source.parent
    return _iter_video_files(source, cfg.input.scan_depth, extensions), source


def probe_video_info(path: Path) -> dict[str, Any]:
    row = {
        "source_path": str(path),
        "opened": False,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "frame_count": 0,
        "duration_sec": 0.0,
        "error": "",
    }
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            row["error"] = "VideoCapture open failed"
            return row
        row["opened"] = True
        row["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        row["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        row["fps"] = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        row["frame_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        row["duration_sec"] = (
            row["frame_count"] / row["fps"] if row["fps"] > 0 and row["frame_count"] > 0 else 0.0
        )
        return row
    finally:
        cap.release()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summarize_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    opened_rows = [row for row in rows if row["opened"]]
    fps_values = sorted({round(float(row["fps"]), 3) for row in opened_rows})
    resolutions = sorted({f"{row['width']}x{row['height']}" for row in opened_rows})
    return {
        "total_files": len(rows),
        "opened_files": len(opened_rows),
        "failed_files": len(rows) - len(opened_rows),
        "fps_values": fps_values,
        "resolutions": resolutions,
    }


def inspect_inputs(cfg: AppConfig, limit: int | None = None, run_dir: str | Path | None = None) -> dict[str, Any]:
    video_paths, input_root = collect_video_paths(cfg)
    if limit is not None:
        video_paths = video_paths[:limit]

    rows: list[dict[str, Any]] = []
    for path in video_paths:
        info = probe_video_info(path)
        try:
            rel = path.relative_to(input_root)
        except ValueError:
            rel = path.name
        info["relative_path"] = str(rel)
        rows.append(info)

    summary = summarize_inventory(rows)
    target_run_dir = Path(run_dir) if run_dir else resolve_run_dir(cfg)
    reports_dir = ensure_dir(target_run_dir / "reports")
    write_csv(reports_dir / "inventory.csv", rows)
    write_json(reports_dir / "inventory_summary.json", summary)
    return {
        "run_dir": str(target_run_dir),
        "input_root": str(input_root),
        "rows": rows,
        "summary": summary,
    }


def validate_transform(cfg: AppConfig) -> None:
    transform = cfg.transform
    if transform.resize_width <= 0 or transform.resize_height <= 0:
        raise ValueError("resize_width/resize_height 는 1 이상이어야 합니다.")
    if transform.target_fps <= 0:
        raise ValueError("target_fps 는 0보다 커야 합니다.")
    if transform.resize_mode not in {"fit_pad", "stretch"}:
        raise ValueError("resize_mode 는 'fit_pad' 또는 'stretch' 여야 합니다.")
    if transform.fps_mode not in {"downsample_only", "strict"}:
        raise ValueError("fps_mode 는 'downsample_only' 또는 'strict' 여야 합니다.")
    out_w = transform.resize_width - transform.crop_left - transform.crop_right
    out_h = transform.resize_height - transform.crop_top - transform.crop_bottom
    if out_w <= 0 or out_h <= 0:
        raise ValueError("crop 값 때문에 최종 해상도가 0 이하가 됩니다.")


def transform_frame(frame: np.ndarray, cfg: AppConfig) -> np.ndarray:
    transform = cfg.transform
    target_w = transform.resize_width
    target_h = transform.resize_height
    if transform.resize_mode == "stretch":
        canvas = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
    else:
        src_h, src_w = frame.shape[:2]
        scale = min(target_w / src_w, target_h / src_h)
        resized_w = max(1, int(round(src_w * scale)))
        resized_h = max(1, int(round(src_h * scale)))
        resized = cv2.resize(frame, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        offset_x = (target_w - resized_w) // 2
        offset_y = (target_h - resized_h) // 2
        canvas[offset_y : offset_y + resized_h, offset_x : offset_x + resized_w] = resized

    top = transform.crop_top
    bottom = transform.crop_bottom
    left = transform.crop_left
    right = transform.crop_right
    end_y = canvas.shape[0] - bottom if bottom > 0 else canvas.shape[0]
    end_x = canvas.shape[1] - right if right > 0 else canvas.shape[1]
    cropped = canvas[top:end_y, left:end_x]
    if cropped.size == 0:
        raise ValueError("transform 결과 프레임이 비었습니다. crop 값을 줄이세요.")
    return cropped


def resolve_roi_boxes(cfg: AppConfig, frame_w: int, frame_h: int) -> list[tuple[int, int, int, int]]:
    if not cfg.roi.enabled or not cfg.roi.boxes:
        return []
    boxes: list[tuple[int, int, int, int]] = []
    for box in cfg.roi.boxes:
        if cfg.roi.space == "pixel":
            x = int(round(box["x"]))
            y = int(round(box["y"]))
            w = int(round(box["w"]))
            h = int(round(box["h"]))
        else:
            x = int(round(box["x"] * frame_w))
            y = int(round(box["y"] * frame_h))
            w = int(round(box["w"] * frame_w))
            h = int(round(box["h"] * frame_h))
        x = max(0, min(frame_w, x))
        y = max(0, min(frame_h, y))
        w = max(0, min(frame_w - x, w))
        h = max(0, min(frame_h - y, h))
        if w > 0 and h > 0:
            boxes.append((x, y, w, h))
    return boxes


def apply_roi_blur(frame: np.ndarray, boxes: list[tuple[int, int, int, int]], kernel: list[int]) -> np.ndarray:
    if not boxes:
        return frame
    out = frame.copy()
    kx = even_positive(kernel[0] if len(kernel) > 0 else 151)
    ky = even_positive(kernel[1] if len(kernel) > 1 else 151)
    for x, y, w, h in boxes:
        roi = out[y : y + h, x : x + w]
        if roi.size == 0:
            continue
        out[y : y + h, x : x + w] = cv2.GaussianBlur(roi, (kx, ky), 0)
    return out


def draw_grid(frame: np.ndarray, interval: int) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    step = max(10, int(interval))
    color = (80, 80, 80)
    for x in range(0, w, step):
        cv2.line(out, (x, 0), (x, h), color, 1)
    for y in range(0, h, step):
        cv2.line(out, (0, y), (w, y), color, 1)
    return out


def draw_rois(frame: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    out = frame.copy()
    palette = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
    ]
    for idx, (x, y, w, h) in enumerate(boxes):
        color = palette[idx % len(palette)]
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        cv2.putText(out, str(idx + 1), (x, max(25, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return out


def save_preview(cfg: AppConfig, run_dir: str | Path | None = None, limit: int | None = None) -> dict[str, Any]:
    validate_transform(cfg)
    inspection = inspect_inputs(cfg, limit=limit, run_dir=run_dir)
    rows = inspection["rows"]
    valid_rows = [row for row in rows if row["opened"]]
    if not valid_rows:
        raise RuntimeError("열 수 있는 영상이 없습니다. inventory.csv 를 확인하세요.")

    video_index = min(max(cfg.preview.video_index, 0), len(valid_rows) - 1)
    target_row = valid_rows[video_index]
    video_path = Path(target_row["source_path"])

    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            raise IOError(f"영상 열기 실패: {video_path}")
        cap.set(cv2.CAP_PROP_POS_FRAMES, cfg.preview.debug_frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise IOError(f"디버그 프레임 읽기 실패: {video_path}")
    finally:
        cap.release()

    transformed = transform_frame(frame, cfg)
    frame_h, frame_w = transformed.shape[:2]
    roi_boxes = resolve_roi_boxes(cfg, frame_w, frame_h)
    preview_dir = ensure_dir(Path(inspection["run_dir"]) / "preview")

    raw_path = preview_dir / "frame_transformed.jpg"
    grid_path = preview_dir / "frame_with_grid.jpg"
    roi_path = preview_dir / "frame_with_rois.jpg"
    cv2.imwrite(str(raw_path), transformed)
    cv2.imwrite(str(grid_path), draw_grid(transformed, cfg.preview.grid_interval))
    cv2.imwrite(str(roi_path), draw_rois(draw_grid(transformed, cfg.preview.grid_interval), roi_boxes))

    preview_info = {
        "video_path": str(video_path),
        "debug_frame_index": cfg.preview.debug_frame_index,
        "preview_paths": {
            "transformed": str(raw_path),
            "grid": str(grid_path),
            "rois": str(roi_path),
        },
        "resolved_rois": [
            {"x": x, "y": y, "w": w, "h": h}
            for x, y, w, h in roi_boxes
        ],
    }
    write_json(Path(inspection["run_dir"]) / "reports" / "preview_info.json", preview_info)
    return {
        **inspection,
        "preview_info": preview_info,
    }


def compute_sample_indices(src_fps: float, total_frames: int, effective_fps: float) -> list[int]:
    if src_fps <= 0 or effective_fps <= 0 or total_frames <= 0:
        return []
    duration = total_frames / src_fps
    frame_total = int(math.ceil(duration * effective_fps))
    indices = []
    for n in range(frame_total):
        source_index = int(round((n / effective_fps) * src_fps))
        if source_index >= total_frames:
            source_index = total_frames - 1
        indices.append(source_index)
    return sorted(set(indices))


def build_sampling_plan(src_fps: float, total_frames: int, cfg: AppConfig) -> tuple[list[int], float, str]:
    target_fps = cfg.transform.target_fps
    if src_fps <= 0:
        raise ValueError("원본 FPS를 읽을 수 없습니다.")
    if cfg.transform.fps_mode == "strict" and src_fps < target_fps:
        raise ValueError(f"원본 FPS({src_fps:.3f})가 target_fps({target_fps:.3f})보다 낮습니다.")
    if cfg.transform.fps_mode == "downsample_only" and src_fps <= target_fps:
        return list(range(total_frames)), src_fps, "source_fps_kept"

    effective_fps = target_fps
    if cfg.transform.preserve_duration:
        return compute_sample_indices(src_fps, total_frames, effective_fps), effective_fps, "time_mapped"

    step = max(1, int(round(src_fps / effective_fps)))
    return list(range(0, total_frames, step)), effective_fps, "step_sampling"


def build_output_path(source_path: Path, input_root: Path, run_dir: Path, cfg: AppConfig) -> Path:
    processed_root = ensure_dir(run_dir / "processed")
    suffix = cfg.output.output_ext.lstrip(".")
    if cfg.input.mode == "file":
        relative_parent = Path()
        stem = source_path.stem
    else:
        relative = source_path.relative_to(input_root)
        relative_parent = relative.parent if cfg.output.preserve_subdirs else Path()
        stem = relative.stem
    output_dir = ensure_dir(processed_root / relative_parent)
    return output_dir / f"{stem}__preprocessed.{suffix}"


def process_video(source_path: Path, input_root: Path, run_dir: Path, cfg: AppConfig) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(source_path))
    writer = None
    result: dict[str, Any] = {
        "source_path": str(source_path),
        "relative_path": str(source_path.relative_to(input_root)) if source_path != input_root else source_path.name,
        "status": "failed",
        "error": "",
        "src_width": 0,
        "src_height": 0,
        "src_fps": 0.0,
        "src_frame_count": 0,
        "sampling_mode": "",
        "dst_path": "",
        "dst_width": 0,
        "dst_height": 0,
        "dst_fps": 0.0,
        "written_frames": 0,
    }
    try:
        if not cap.isOpened():
            raise IOError("VideoCapture open failed")
        result["src_width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        result["src_height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        result["src_fps"] = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        result["src_frame_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_indices, effective_fps, sampling_mode = build_sampling_plan(
            result["src_fps"], result["src_frame_count"], cfg
        )
        result["sampling_mode"] = sampling_mode
        result["dst_fps"] = round(effective_fps, 6)

        ok, first_frame = cap.read()
        if not ok or first_frame is None:
            raise IOError("첫 프레임 읽기 실패")
        transformed_first = transform_frame(first_frame, cfg)
        dst_h, dst_w = transformed_first.shape[:2]
        result["dst_width"] = dst_w
        result["dst_height"] = dst_h
        roi_boxes = resolve_roi_boxes(cfg, dst_w, dst_h)
        output_path = build_output_path(source_path, input_root, run_dir, cfg)
        writer = cv2.VideoWriter(
            str(output_path),
            fourcc_for_ext(cfg.output.output_ext),
            effective_fps,
            (dst_w, dst_h),
        )
        if not writer.isOpened():
            raise IOError(f"VideoWriter open failed: {output_path}")
        result["dst_path"] = str(output_path)

        pointer = 0
        total_needed = len(sample_indices)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        current_index = 0
        while pointer < total_needed:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            wanted = sample_indices[pointer]
            if current_index == wanted:
                transformed = transform_frame(frame, cfg)
                transformed = apply_roi_blur(transformed, roi_boxes, cfg.roi.blur_kernel)
                writer.write(transformed)
                result["written_frames"] += 1
                if result["written_frames"] % cfg.run.log_every == 0:
                    print(f"[{source_path.name}] written_frames={result['written_frames']}")
                pointer += 1
            current_index += 1

        if result["written_frames"] <= 0:
            raise RuntimeError("출력 프레임이 0개입니다.")
        result["status"] = "ok"
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        return result
    finally:
        cap.release()
        if writer is not None:
            writer.release()


def run_batch(
    cfg: AppConfig,
    limit: int | None = None,
    dry_run: bool = False,
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    validate_transform(cfg)
    prepared_run_dir = Path(run_dir) if run_dir else resolve_run_dir(cfg)
    inspection = inspect_inputs(cfg, limit=limit, run_dir=prepared_run_dir)
    video_paths, input_root = collect_video_paths(cfg)
    if limit is not None:
        video_paths = video_paths[:limit]

    if cfg.preview.enabled:
        save_preview(cfg, run_dir=prepared_run_dir, limit=limit)

    reports_dir = ensure_dir(prepared_run_dir / "reports")
    if dry_run:
        summary = {
            "run_dir": str(prepared_run_dir),
            "dry_run": True,
            "planned_files": len(video_paths),
            "inventory_summary": inspection["summary"],
        }
        write_json(reports_dir / "run_summary.json", summary)
        return summary

    success_rows: list[dict[str, Any]] = []
    failed_rows: list[dict[str, Any]] = []
    for path in video_paths:
        row = process_video(path, input_root, prepared_run_dir, cfg)
        if row["status"] == "ok":
            success_rows.append(row)
        else:
            failed_rows.append(row)
            print(f"[WARN] failed: {path} -> {row['error']}")
            if not cfg.run.continue_on_error:
                break

    write_csv(reports_dir / "success.csv", success_rows)
    write_csv(reports_dir / "failed.csv", failed_rows)
    summary = {
        "run_dir": str(prepared_run_dir),
        "dry_run": False,
        "requested_files": len(video_paths),
        "success_count": len(success_rows),
        "failed_count": len(failed_rows),
        "inventory_summary": inspection["summary"],
        "config": asdict(cfg),
    }
    write_json(reports_dir / "run_summary.json", summary)
    return summary

