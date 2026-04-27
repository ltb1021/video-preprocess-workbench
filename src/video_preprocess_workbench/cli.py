from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import create_example_config, load_config
from .pipeline import apply_overrides, inspect_inputs, run_batch, save_preview


def _common_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-path", help="config 의 input.path 를 일회성 override")
    parser.add_argument("--output-dir", help="config 의 output.base_dir 를 일회성 override")
    parser.add_argument(
        "--scan-depth",
        type=int,
        help="0=root only, 1=one level, -1=recursive all. config 값 override",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-preprocess-lab",
        description="Batch video preprocessing with scan depth control, preview, ROI blur, and CSV reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-config", help="예제 config JSON 생성")
    init_parser.add_argument("destination", help="생성할 JSON 경로")
    init_parser.add_argument("--force", action="store_true", help="기존 파일이 있어도 덮어쓰기")

    inspect_parser = subparsers.add_parser("inspect", help="영상 목록과 메타데이터 inventory 생성")
    inspect_parser.add_argument("config", help="config JSON 경로")
    inspect_parser.add_argument("--limit", type=int, default=None, help="앞에서 N개만 검사")
    _common_override_args(inspect_parser)

    preview_parser = subparsers.add_parser("preview", help="대표 영상 1개 preview 이미지 저장")
    preview_parser.add_argument("config", help="config JSON 경로")
    preview_parser.add_argument("--limit", type=int, default=None, help="앞에서 N개만 사용")
    _common_override_args(preview_parser)

    run_parser = subparsers.add_parser("run", help="전체 배치 전처리 실행")
    run_parser.add_argument("config", help="config JSON 경로")
    run_parser.add_argument("--limit", type=int, default=None, help="앞에서 N개만 실행")
    run_parser.add_argument("--dry-run", action="store_true", help="실제 인코딩 없이 scan/report만 수행")
    _common_override_args(run_parser)
    return parser


def _load_with_overrides(args: argparse.Namespace):
    cfg = load_config(args.config)
    scan_depth = args.scan_depth
    if scan_depth == -1:
        scan_depth = None
    if scan_depth is None and getattr(args, "scan_depth", None) == -1:
        scan_depth = None
    override_marker = scan_depth if getattr(args, "scan_depth", None) is not None else ...
    return apply_overrides(
        cfg,
        input_path=args.input_path,
        output_dir=args.output_dir,
        scan_depth=override_marker,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-config":
        target = Path(args.destination).expanduser().resolve()
        if target.exists() and not args.force:
            parser.error(f"이미 파일이 있습니다: {target} (덮어쓰려면 --force)")
        created = create_example_config(target)
        print(created)
        return 0

    cfg = _load_with_overrides(args)

    if args.command == "inspect":
        result = inspect_inputs(cfg, limit=args.limit)
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
        print(result["run_dir"])
        return 0

    if args.command == "preview":
        result = save_preview(cfg, limit=args.limit)
        print(json.dumps(result["preview_info"], indent=2, ensure_ascii=False))
        print(result["run_dir"])
        return 0

    if args.command == "run":
        result = run_batch(cfg, limit=args.limit, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    parser.error("알 수 없는 명령입니다.")
    return 2
