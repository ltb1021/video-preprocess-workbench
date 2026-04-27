# video-preprocess-workbench

여러 PC에서 재사용할 수 있게 만든 범용 영상 전처리 도구다.  
폴더 또는 단일 영상 경로를 받아서 `scan depth` 제어, 메타데이터 inventory 생성, preview 이미지 저장, 배치 resize/FPS 변환/ROI blur 처리, 성공/실패 CSV 기록까지 한 번에 수행한다.

## 현재 상황

- 확인된 사실:
  - 기존 notebook은 단일 `video_path` 중심이라 폴더 전체 처리, 하위 폴더 스캔, 실패 파일 분리 기록이 약했다.
  - 이 저장소는 그 흐름을 `config JSON + CLI + notebook helper` 구조로 일반화한 버전이다.
- 확인된 사실:
  - 입력 경로는 config 파일 기준 상대경로도 되고, CLI에서 절대경로로 override 해도 된다.
  - 하위 폴더 전체 스캔은 `scan_depth = -1` 또는 config 에서 `null` 개념 대신 CLI override `--scan-depth -1`로 사용할 수 있다.

## 추천 사용 흐름

1. `init-config` 로 개인용 config 를 하나 만든다.
2. `inspect` 로 영상 개수, 해상도, FPS 분포를 먼저 확인한다.
3. `preview` 로 대표 프레임에 grid/ROI overlay 를 저장해 설정이 맞는지 본다.
4. `run --dry-run` 으로 실제 인코딩 전 보고서만 생성해 본다.
5. 문제가 없으면 `run` 으로 전체 배치 처리한다.

## 프로젝트 구조

```text
video-preprocess-workbench/
├── README.md
├── artifacts/
├── configs/
│   └── example_batch.json
├── notebooks/
│   └── video_preprocess_demo.ipynb
├── pyproject.toml
├── requirements.txt
├── src/
│   └── video_preprocess_workbench/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       └── pipeline.py
└── video_preprocess_cli.py
```

## 설치

```bash
cd /share_ssd/ltb/Users/ltb/git_repos/video-preprocess-workbench
python -m pip install -r requirements.txt
```

## 빠른 시작

### 1. 예제 config 생성

```bash
python video_preprocess_cli.py init-config ./configs/local_batch.json
```

### 2. config 수정

`configs/local_batch.json` 에서 보통 아래만 먼저 바꾸면 된다.

```json
{
  "input": {
    "path": "/your/video/folder",
    "mode": "dir",
    "scan_depth": 0
  },
  "output": {
    "base_dir": "../artifacts/runs"
  }
}
```

자주 쓰는 값:

- `scan_depth: 0`
  - 입력 폴더 바로 아래 영상만 처리
- `scan_depth: 1`
  - 한 단계 하위 폴더까지 처리
- CLI `--scan-depth -1`
  - 전체 재귀 스캔

### 3. inventory 생성

```bash
python video_preprocess_cli.py inspect ./configs/local_batch.json
```

생성물:

- `artifacts/runs/run_YYYYMMDD_HHMMSS/reports/inventory.csv`
- `artifacts/runs/run_YYYYMMDD_HHMMSS/reports/inventory_summary.json`

### 4. preview 저장

```bash
python video_preprocess_cli.py preview ./configs/local_batch.json
```

생성물:

- `preview/frame_transformed.jpg`
- `preview/frame_with_grid.jpg`
- `preview/frame_with_rois.jpg`

### 5. dry-run

```bash
python video_preprocess_cli.py run ./configs/local_batch.json --dry-run
```

### 6. 실제 실행

```bash
python video_preprocess_cli.py run ./configs/local_batch.json
```

## CLI override 예시

config 를 매번 고치지 않고 일회성으로 경로만 바꿀 수 있다.

```bash
python video_preprocess_cli.py inspect ./configs/example_batch.json \
  --input-path '/share_ssd/ltb/Users/ltb/박스_추론용_샘플영상들/260413_배테스트용_영상들' \
  --scan-depth 0
```

전체 하위 폴더까지 스캔:

```bash
python video_preprocess_cli.py inspect ./configs/example_batch.json \
  --input-path '/share_ssd/ltb/Users/ltb/박스_추론용_샘플영상들/260413_배테스트용_영상들' \
  --scan-depth -1
```

## 주요 설정 설명

### input

- `path`: 단일 파일 또는 폴더
- `mode`: `"file"` 또는 `"dir"`
- `scan_depth`: `0`, `1`, `2` ... 또는 CLI에서 `-1`
- `extensions`: 스캔할 확장자 목록

### output

- `base_dir`: run 결과가 쌓일 루트
- `run_name`: `"auto"` 이면 timestamp 기반 자동 생성
- `output_ext`: 기본 출력 확장자
- `preserve_subdirs`: 폴더 모드일 때 원본 하위 구조 유지 여부

### transform

- `resize_mode`
  - `"fit_pad"`: 비율 유지 후 padding. 일반적으로 추천
  - `"stretch"`: 강제 resize. 원본 비율 왜곡 가능
- `resize_width`, `resize_height`: target canvas 크기
- `crop_*`: resize 뒤 잘라낼 margin
- `target_fps`: 목표 FPS
- `fps_mode`
  - `"downsample_only"`: 원본 FPS가 더 낮으면 원본 FPS 유지
  - `"strict"`: 원본 FPS가 더 낮으면 실패로 기록
- `preserve_duration`: 길이 보존형 time-mapped 샘플링 사용 여부

### roi

- `enabled`: ROI blur 사용 여부
- `space`
  - `"normalized"`: `0.0 ~ 1.0` 비율 좌표. 여러 해상도에 가장 안전
  - `"pixel"`: 고정 pixel 좌표
- `boxes`: ROI 목록
- `blur_kernel`: Gaussian blur kernel 크기

## 출력 구조

실행 후 기본적으로 아래 구조가 생성된다.

```text
artifacts/runs/run_YYYYMMDD_HHMMSS/
├── preview/
├── processed/
└── reports/
    ├── inventory.csv
    ├── inventory_summary.json
    ├── preview_info.json
    ├── success.csv
    ├── failed.csv
    └── run_summary.json
```

## Notebook 사용

- 예제 notebook: [notebooks/video_preprocess_demo.ipynb](/share_ssd/ltb/Users/ltb/git_repos/video-preprocess-workbench/notebooks/video_preprocess_demo.ipynb)
- notebook 에서는 Python 함수로 직접 `inspect_inputs`, `save_preview`, `run_batch` 를 호출할 수 있다.
- config 세부 항목 설명은 [docs/config_guide_ko.md](/share_ssd/ltb/Users/ltb/git_repos/video-preprocess-workbench/docs/config_guide_ko.md) 를 참고하면 된다.

## Python에서 직접 사용

```python
from pathlib import Path
import sys

project_root = Path.cwd()
sys.path.insert(0, str(project_root / "src"))

from video_preprocess_workbench import load_config, inspect_inputs, save_preview, run_batch
from video_preprocess_workbench.pipeline import apply_overrides

cfg = load_config("./configs/example_batch.json")
cfg = apply_overrides(
    cfg,
    input_path="/your/video/folder",
    output_dir="./artifacts/runs",
    scan_depth=0,
)

inspection = inspect_inputs(cfg)
preview = save_preview(cfg, run_dir=inspection["run_dir"])
summary = run_batch(cfg, dry_run=True, run_dir=inspection["run_dir"])
print(inspection["summary"])
print(preview["preview_info"])
print(summary)
```

## 검증 포인트

- `inspect` 결과에서 `failed_files` 가 0이 아닌지 확인
- `preview/frame_with_rois.jpg` 에서 ROI 위치가 맞는지 확인
- `run --dry-run` 후 `run_summary.json` 확인
- 실제 실행 후 `failed.csv` 가 비어 있는지 확인

## 주의

- 이 repo는 raw 영상 자체를 포함하지 않는다.
- 개인 입력 영상 폴더는 `configs/local_*.json` 같은 개인 config 에서만 참조하는 것을 권장한다.
- `fit_pad` 는 비율 유지에 유리하지만, padding 이 들어가므로 ROI를 pixel 기준으로 쓸 때는 preview 확인이 필요하다.
