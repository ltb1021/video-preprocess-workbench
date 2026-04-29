# Config Guide (Korean)

이 문서는 `configs/example_batch.json`, `configs/example_segment.json` 의 각 항목을 실무 관점에서 설명한다.

## 1. input

```json
"input": {
  "path": "../input_videos",
  "mode": "dir",
  "scan_depth": 0,
  "extensions": [".mp4", ".avi", ".mov", ".mkv"]
}
```

- `path`
  - 단일 파일 또는 폴더 경로다.
  - 상대경로면 config 파일 위치 기준으로 해석된다.
- `mode`
  - `"file"`: 파일 1개만 처리
  - `"dir"`: 폴더 스캔 후 여러 파일 처리
- `scan_depth`
  - `0`: 입력 폴더 바로 아래 파일만 처리
  - `1`: 한 단계 하위 폴더까지 포함
  - `2`: 두 단계 하위까지 포함
  - CLI `--scan-depth -1`: 전체 재귀 스캔
- `extensions`
  - 스캔할 영상 확장자 목록

추천:
- 일반 샘플 폴더: `scan_depth = 0`
- 데이터셋 구조가 `Videos/` 같은 하위 폴더에 들어간 경우: `scan_depth = 2` 또는 CLI `-1`

## 2. output

```json
"output": {
  "base_dir": "../artifacts/runs",
  "run_name": "auto",
  "output_ext": "mp4",
  "preserve_subdirs": true
}
```

- `base_dir`
  - run 결과가 쌓이는 루트 폴더
- `run_name`
  - `"auto"`면 `run_YYYYMMDD_HHMMSS` 형식 자동 생성
  - 고정 문자열을 넣으면 같은 이름 폴더를 계속 쓰게 되므로 보통 `auto` 추천
- `output_ext`
  - 기본 출력 확장자
- `preserve_subdirs`
  - `true`: 원본 하위 폴더 구조 유지
  - `false`: 처리 결과를 한 폴더에 평평하게 저장

추천:
- 중복 파일명이 있을 수 있는 데이터셋은 `preserve_subdirs = true`

## 3. transform

```json
"transform": {
  "resize_mode": "fit_pad",
  "resize_width": 1280,
  "resize_height": 720,
  "crop_top": 0,
  "crop_bottom": 0,
  "crop_left": 0,
  "crop_right": 0,
  "target_fps": 10.0,
  "fps_mode": "downsample_only",
  "preserve_duration": true
}
```

- `resize_mode`
  - `"fit_pad"`: 비율 유지 후 남는 공간을 padding. 가장 안전
  - `"stretch"`: 무조건 target size 로 늘이거나 줄임. 비율 왜곡 가능
- `resize_width`, `resize_height`
  - target canvas 크기
- `crop_*`
  - resize 뒤 잘라낼 pixel 수
- `target_fps`
  - 원하는 출력 FPS
- `fps_mode`
  - `"downsample_only"`: 원본 FPS가 더 낮으면 억지로 올리지 않고 원본 FPS 유지
  - `"strict"`: 원본 FPS가 더 낮으면 실패 처리
- `preserve_duration`
  - `true`: 길이 보존형 샘플링
  - `false`: step 기반 단순 샘플링

추천:
- 초보자 기본값은 `fit_pad + downsample_only + preserve_duration = true`

## 4. roi

```json
"roi": {
  "enabled": false,
  "space": "normalized",
  "boxes": [
    {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.15}
  ],
  "blur_kernel": [151, 151]
}
```

- `enabled`
  - ROI blur 사용 여부
- `space`
  - `"normalized"`: 0.0~1.0 비율 좌표
  - `"pixel"`: 고정 pixel 좌표
- `boxes`
  - ROI 목록
- `blur_kernel`
  - Gaussian blur kernel 크기

추천:
- 여러 해상도 영상이 섞이면 `normalized`
- 해상도가 완전히 고정된 현장 영상이면 `pixel` 도 가능

## 5. preview

```json
"preview": {
  "enabled": true,
  "video_index": 0,
  "debug_frame_index": 0,
  "grid_interval": 50
}
```

- `enabled`
  - batch run 전에 preview 이미지를 저장할지 여부
- `video_index`
  - inventory 에서 몇 번째 영상을 대표 샘플로 볼지
- `debug_frame_index`
  - 해당 영상에서 몇 번째 프레임을 preview 할지
- `grid_interval`
  - grid 간격

추천:
- ROI 튜닝 중이면 `enabled = true`
- 대량 반복 batch에서 속도가 중요하면 `false` 가능

## 6. run

```json
"run": {
  "continue_on_error": true,
  "log_every": 50
}
```

- `continue_on_error`
  - 한 파일 실패 시 다음 파일 계속 진행할지 여부
- `log_every`
  - 몇 프레임마다 진행 로그를 찍을지

추천:
- 실무에서는 보통 `continue_on_error = true`

## 7. segment

```json
"segment": {
  "start_sec": 290.0,
  "end_sec": 350.0,
  "preserve_source_fps": true
}
```

- `start_sec`
  - 구간 시작 시각(초)
- `end_sec`
  - 구간 종료 시각(초)
- `preserve_source_fps`
  - `true` 면 파일별 원본 FPS 그대로 저장

설명:
- `4분 50초 ~ 5분 50초` 를 잘라내고 싶으면 `290.0 ~ 350.0` 으로 넣으면 된다.
- 파일마다 FPS가 조금 달라도, `preserve_source_fps = true` 이면 각 파일 고유 FPS를 유지한다.

추천:
- CCTV 원본 비교용 편집이면 `preserve_source_fps = true` 유지
- `scan_depth = 0` 으로 폴더 바로 아래 3개 파일만 먼저 처리하는 것을 추천

## 자주 쓰는 예시

### 예시 1. 폴더 바로 아래 파일만 처리

```json
"input": {
  "path": "/data/sample_videos",
  "mode": "dir",
  "scan_depth": 0
}
```

### 예시 2. `Videos/` 하위 폴더까지 포함

```bash
python video_preprocess_cli.py inspect ./configs/example_batch.json \
  --input-path '/data/ship_dataset' \
  --scan-depth -1
```

### 예시 3. 세로 영상이 섞였을 때

- `resize_mode = "fit_pad"` 추천
- `stretch` 는 피하는 편이 안전

### 예시 4. 원본 FPS보다 높은 target_fps를 넣고 싶지 않을 때

- `fps_mode = "downsample_only"` 유지
- 그러면 원본이 8 FPS인데 target이 10 FPS여도 억지 증간 없이 8 FPS 유지

### 예시 5. 4분 50초 ~ 5분 50초 구간만 자르기

```json
"segment": {
  "start_sec": 290.0,
  "end_sec": 350.0,
  "preserve_source_fps": true
}
```

CLI 예시:

```bash
python video_preprocess_cli.py segment ./configs/example_segment.json \
  --input-path '/share_ssd/ltb/Users/ltb/박스_추론용_샘플영상들/260429_서초서리풀_영건님이_프레임시간순서맞춘_3개_cctv영상들/cropped_1500sec' \
  --scan-depth 0
```
