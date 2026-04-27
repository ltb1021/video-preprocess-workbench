"""
CLI entrypoint for video-preprocess-workbench.

이 파일의 목표:
1. 초보자도 `--help` 만 보고 바로 따라할 수 있게 안내한다.
2. config 파일을 고정해 두고, 경로만 CLI 에서 일회성 override 할 수 있게 한다.
3. inspect -> preview -> run 순서를 강제하지는 않지만, 자연스럽게 유도한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import create_example_config, load_config
from .pipeline import apply_overrides, inspect_inputs, run_batch, save_preview


def _common_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input-path",
        help=(
            "config 의 input.path 를 일회성 override.\n"
            "예: 특정 PC 에서만 다른 원본 영상 폴더를 잠깐 지정하고 싶을 때 사용"
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "config 의 output.base_dir 를 일회성 override.\n"
            "예: 외장 SSD 나 다른 작업 폴더로 결과를 빼고 싶을 때 사용"
        ),
    )
    parser.add_argument(
        "--scan-depth",
        type=int,
        help=(
            "폴더 스캔 깊이 override.\n"
            "0=root 바로 아래만, 1=한 단계 하위까지, -1=전체 재귀 스캔"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-preprocess-lab",
        description=(
            "영상 폴더 또는 단일 파일을 대상으로 메타데이터 검사, preview, 배치 전처리를 수행합니다."
        ),
        epilog=(
            "권장 순서:\n"
            "  1) init-config 로 내 설정 파일 만들기\n"
            "  2) inspect 로 영상 개수/해상도/FPS 확인\n"
            "  3) preview 로 대표 프레임과 ROI 확인\n"
            "  4) run --dry-run 으로 보고서만 먼저 확인\n"
            "  5) run 으로 실제 변환\n"
            "\n"
            "예시:\n"
            "  python video_preprocess_cli.py init-config ./configs/local_batch.json\n"
            "  python video_preprocess_cli.py inspect ./configs/local_batch.json\n"
            "  python video_preprocess_cli.py inspect ./configs/example_batch.json --input-path '/data/videos' --scan-depth 0\n"
            "  python video_preprocess_cli.py preview ./configs/example_batch.json --input-path '/data/videos' --scan-depth -1\n"
            "  python video_preprocess_cli.py run ./configs/example_batch.json --input-path '/data/videos' --scan-depth -1 --dry-run\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init-config",
        help="예제 config JSON 생성",
        description=(
            "새 PC 또는 새 프로젝트에서 출발할 때 사용할 기본 config JSON 을 만듭니다.\n"
            "보통 이 파일을 복사해서 개인용 local config 로 씁니다."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    init_parser.add_argument("destination", help="생성할 JSON 경로. 예: ./configs/local_batch.json")
    init_parser.add_argument("--force", action="store_true", help="기존 파일이 있어도 덮어쓰기")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="영상 목록과 메타데이터 inventory 생성",
        description=(
            "입력 경로를 스캔해서 영상별 해상도, FPS, frame count, duration 을 CSV 로 저장합니다.\n"
            "실제 인코딩은 하지 않으므로 가장 먼저 실행하는 것을 권장합니다."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    inspect_parser.add_argument("config", help="config JSON 경로")
    inspect_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="앞에서 N개만 검사. 대형 폴더에서 샘플 검증할 때 유용",
    )
    _common_override_args(inspect_parser)

    preview_parser = subparsers.add_parser(
        "preview",
        help="대표 영상 1개 preview 이미지 저장",
        description=(
            "대표 영상 1개를 골라 resize/crop 적용 후 grid/ROI overlay 미리보기를 저장합니다.\n"
            "ROI 좌표가 맞는지, 세로 영상이 찌그러지지 않는지 확인할 때 사용합니다."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    preview_parser.add_argument("config", help="config JSON 경로")
    preview_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="앞에서 N개만 스캔해서 preview 대상 범위를 줄임",
    )
    _common_override_args(preview_parser)

    run_parser = subparsers.add_parser(
        "run",
        help="전체 배치 전처리 실행",
        description=(
            "실제 인코딩을 수행합니다.\n"
            "먼저 --dry-run 으로 inventory/preview/report 부터 점검한 뒤 실제 run 을 권장합니다."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    run_parser.add_argument("config", help="config JSON 경로")
    run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="앞에서 N개만 실행. 소량 smoke test 용도",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 인코딩 없이 scan/report/preview 만 수행",
    )
    _common_override_args(run_parser)
    return parser


def _load_with_overrides(args: argparse.Namespace):
    cfg = load_config(args.config)
    scan_depth = args.scan_depth
    if scan_depth == -1:
        scan_depth = None
    if scan_depth is None and getattr(args, "scan_depth", None) == -1:
        scan_depth = None

    # override 를 주지 않았으면 config 원본 값을 그대로 쓴다.
    # override 를 줬으면 그 값만 일회성으로 덮어쓴다.
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
        print("# inventory summary")
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
        print("# run_dir")
        print(result["run_dir"])
        return 0

    if args.command == "preview":
        result = save_preview(cfg, limit=args.limit)
        print("# preview info")
        print(json.dumps(result["preview_info"], indent=2, ensure_ascii=False))
        print("# run_dir")
        print(result["run_dir"])
        return 0

    if args.command == "run":
        result = run_batch(cfg, limit=args.limit, dry_run=args.dry_run)
        print("# run summary")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    parser.error("알 수 없는 명령입니다.")
    return 2
