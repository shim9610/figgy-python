# Windows RTX 4070 Ti 벤치마크

fastplotlib·VisPy·pyqtgraph OpenGL을 추가한 최신 비교는 [GPU 라이브러리 벤치마크](WINDOWS_GPU_RESULTS.md)를 참고합니다. 아래 pyqtgraph 결과는 이전 QPainter 경로입니다.

2026-10-14 (Asia/Seoul), 설치한 Windows release wheel에서 측정했습니다.

## 환경과 방법

- 소스 커밋: `ff4bf0cf2d2f8457434abc211c71201e30a09101`. 벤치마크 실행 코드와 native 바인딩은 이 커밋 그대로입니다.
- Windows-11-10.0.26300-SP0, Python 3.13.1, Rust 1.99.0 / MSVC.
- Intel Core i7-13700KF, 16코어 / 24스레드, 시스템 메모리 약 64 GiB.
- NVIDIA GeForce RTX 4070 Ti, 12,282 MiB VRAM, NVIDIA 드라이버 617.14.
- Figgy가 기본 선택한 **Vulkan / DiscreteGpu**를 사용했습니다. DX12 측정은 아닙니다.
- 960×600 완료된 RGBA readback, 동일 float64 입력, 독립 프로세스, 반복 5회 중앙값.
- 초기화, 등록/fit, 첫 draw, 반복 draw, 축/스타일 변경, PNG 렌더+인코딩, worker peak RSS를 구분합니다.
- import와 입력 생성은 타이밍에서 제외합니다. OS/font/driver shader cache는 초기화하지 않습니다.
- Figgy는 전체 데이터를 상주시키고 다운샘플링하지 않습니다. 반복 렌더 후 column upload는 선·산점도에서 2회이며, 히트맵은 행별 열과 좌표 열을 합해 318/1,002/2,002회입니다.
- matplotlib 기본 단순화/단순화 해제와 pyqtgraph 기본 QPainter(AA off / OpenGL off / autoDownsample off)를 비교합니다.
- GPU surface FPS, Qt 창 또는 Jupyter의 표시 지연 측정이 아닙니다. AA 방식과 이미지 픽셀은 백엔드마다 다릅니다.
- RSS는 입력·라이브러리·드라이버를 포함한 프로세스 메모리이며 VRAM 측정치가 아닙니다.

## 대표 결과

| 작업 | Figgy 반복 (ms) | matplotlib 기본 반복 (ms) | 반복 속도비 | Figgy 첫 프레임 (ms) | matplotlib 첫 프레임 (ms) |
|---|---:|---:|---:|---:|---:|
| 500만 점 매끄러운 선 | 9.28 | 99.66 | 10.7× | 462.78 | 290.72 |
| 500만 점 잡음 선 | 18.44 | 206.36 | 11.2× | 479.91 | 416.62 |
| 500만 점 산점도 | 9.40 | 1353.27 | 144.0× | 659.45 | 1481.04 |
| 400만 셀 히트맵 | 1.31 | 123.39 | 94.1× | 668.28 | 154.53 |

위 속도비는 이 PC에서의 반복 RGBA 렌더만 비교합니다. 초기화·업로드 비용과 PNG 인코딩, UI 전달 비용은 별도로 봐야 합니다.

비교 결과를 요약한 차트도 `benchmarks/plot_results.py`가 Figgy로 직접 렌더합니다.
선·점·축·범례·제목은 모두 Rust figgy-renderer에서 그립니다. 현재 Python API는 한 패널만
지원하므로, 완성된 네 패널과 제목의 픽셀을 Pillow로 배치하고 PNG로 저장합니다.
SVG 파일은 이 PNG를 내장한 컨테이너이며 벡터 export가 아닙니다.
보고용 차트 생성 시간은 벤치마크 수치에 포함하지 않았습니다.
[차트 렌더링 기록](results/windows-rtx4070ti-comparison.rendering.json)에 각 패널의 실제 어댑터를 기록했습니다.

## 전체 측정

| 작업 | 신호 | 입력 수 | 백엔드 | 상태 | 첫 프레임 (ms) | 반복 (ms) | 축 변경 (ms) | 스타일 변경 (ms) | PNG (ms) | Peak RSS (MiB) |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| line | smooth | 100,000 | figgy | ok | 403.22 | 1.11 | 2.66 | 2.95 | 14.91 | 192.5 |
| line | smooth | 100,000 | matplotlib-default | ok | 32.03 | 11.68 | 11.17 | 11.38 | 26.85 | 76.1 |
| line | smooth | 100,000 | matplotlib-unsimplified | ok | 37.09 | 18.79 | 17.56 | 17.23 | 32.95 | 76.3 |
| line | smooth | 100,000 | pyqtgraph-default | ok | 95.78 | 38.71 | 41.01 | 39.20 | 50.10 | 112.1 |
| line | smooth | 1,000,000 | figgy | ok | 414.79 | 1.88 | 3.47 | 3.71 | 16.59 | 207.1 |
| line | smooth | 1,000,000 | matplotlib-default | ok | 78.51 | 28.61 | 27.81 | 28.13 | 43.46 | 117.2 |
| line | smooth | 1,000,000 | matplotlib-unsimplified | ok | 141.41 | 88.68 | 88.07 | 87.85 | 103.67 | 128.0 |
| line | smooth | 1,000,000 | pyqtgraph-default | ok | 734.77 | 350.13 | 355.78 | 357.83 | 361.77 | 152.9 |
| line | smooth | 5,000,000 | figgy | ok | 462.78 | 9.28 | 10.78 | 10.90 | 24.18 | 267.8 |
| line | smooth | 5,000,000 | matplotlib-default | ok | 290.72 | 99.66 | 97.54 | 98.70 | 111.73 | 385.4 |
| line | smooth | 5,000,000 | matplotlib-unsimplified | ok | 618.38 | 420.79 | 421.03 | 419.74 | 430.68 | 396.8 |
| line | smooth | 5,000,000 | pyqtgraph-default | ok | 3589.82 | 1734.53 | 1747.75 | 1778.60 | 1760.41 | 335.9 |
| line | noisy | 100,000 | figgy | ok | 418.76 | 1.37 | 2.82 | 2.88 | 17.77 | 196.7 |
| line | noisy | 100,000 | matplotlib-default | ok | 92.66 | 61.72 | 65.59 | 64.69 | 79.72 | 117.8 |
| line | noisy | 100,000 | matplotlib-unsimplified | ok | 187.23 | 135.12 | 134.79 | 134.09 | 148.68 | 167.0 |
| line | noisy | 100,000 | pyqtgraph-default | ok | 120.79 | 56.10 | 59.79 | 58.25 | 69.57 | 117.2 |
| line | noisy | 1,000,000 | figgy | ok | 425.86 | 4.02 | 5.52 | 5.76 | 20.86 | 209.2 |
| line | noisy | 1,000,000 | matplotlib-default | ok | 175.67 | 108.77 | 117.17 | 115.93 | 130.39 | 180.1 |
| line | noisy | 1,000,000 | matplotlib-unsimplified | ok | 2100.21 | 1821.58 | 1847.60 | 1838.03 | 1810.03 | 986.0 |
| line | noisy | 1,000,000 | pyqtgraph-default | ok | 962.91 | 475.21 | 478.19 | 484.87 | 491.63 | 158.2 |
| line | noisy | 5,000,000 | figgy | ok | 479.91 | 18.44 | 20.04 | 20.00 | 37.84 | 270.6 |
| line | noisy | 5,000,000 | matplotlib-default | ok | 416.62 | 206.36 | 215.58 | 215.48 | 237.16 | 390.5 |
| line | noisy | 5,000,000 | matplotlib-unsimplified | error | — | — | — | — | — | — |
| line | noisy | 5,000,000 | pyqtgraph-default | ok | 4669.31 | 2301.23 | 2311.56 | 2344.90 | 2317.69 | 341.8 |
| scatter | noisy | 100,000 | figgy | ok | 413.33 | 1.31 | 2.76 | 2.99 | 32.64 | 196.4 |
| scatter | noisy | 100,000 | matplotlib-default | ok | 67.38 | 36.99 | 37.01 | 37.76 | 54.42 | 76.4 |
| scatter | noisy | 1,000,000 | figgy | ok | 439.39 | 2.56 | 4.27 | 4.30 | 37.17 | 210.1 |
| scatter | noisy | 1,000,000 | matplotlib-default | ok | 317.57 | 280.18 | 279.40 | 280.05 | 294.26 | 126.2 |
| scatter | noisy | 5,000,000 | figgy | ok | 659.45 | 9.40 | 11.10 | 11.92 | 46.58 | 270.9 |
| scatter | noisy | 5,000,000 | matplotlib-default | ok | 1481.04 | 1353.27 | 1348.71 | 1345.52 | 1352.15 | 399.0 |
| heatmap | smooth | 99,856 | figgy | ok | 426.76 | 1.04 | 2.96 | — | 23.10 | 200.2 |
| heatmap | smooth | 99,856 | matplotlib-default | ok | 56.84 | 32.09 | 30.53 | — | 50.31 | 103.3 |
| heatmap | smooth | 1,000,000 | figgy | ok | 479.37 | 1.34 | 3.18 | — | 59.24 | 206.5 |
| heatmap | smooth | 1,000,000 | matplotlib-default | ok | 79.73 | 53.80 | 52.06 | — | 85.96 | 151.4 |
| heatmap | smooth | 4,000,000 | figgy | ok | 668.28 | 1.31 | 3.25 | — | 59.03 | 235.2 |
| heatmap | smooth | 4,000,000 | matplotlib-default | ok | 154.53 | 123.39 | 121.03 | — | 152.59 | 385.6 |

총 36개 조합 중 성공 35개, 오류 1개, timeout 0개입니다. Figgy의 모든 입력은 성공했습니다. 오류 행과 원문은 JSON에 보존했습니다.

- matplotlib-unsimplified / line / noisy / 5,000,000: `OverflowError: Exceeded cell block limit in Agg`. 기본 matplotlib는 같은 입력을 완료했습니다.
- pyqtgraph AA on 탐색은 본 비교에서 제외했으며, 완료된 일부 측정은 로컬 `results/exploratory-windows-pyqtgraph-aa.json`에 보관했습니다. 전체 조합 측정으로 취급하지 않습니다.

## 설치와 기능 확인

- `python -m pip install ".[desktop,notebook,benchmark,test]"`로 CPython 3.13 Windows x64 release wheel을 빌드·설치했습니다.
- Chrome을 연결한 전체 pytest: **9 passed, 1 skipped**. 건너뛴 항목은 128 MiB 이하 디바이스를 대상으로 하는 할당 실패 검사입니다. 이 GPU의 열 풀 한도는 약 2 GiB입니다.
- 이후 로그 축 Python API를 추가한 설치본에서는 **11 passed, 1 skipped**를 확인했습니다. 추가 검사에서 로그 축의 native 렌더·피킹과 잘못된 축 변경의 원자성을 확인했습니다.
- 브라우저 통합 검사에서 제목 편집, 선택·드래그, Python 코드 클립보드 복사, PNG 다운로드가 통과했습니다.
- 실제 QtWebEngine 창에서 `examples/quickstart.py`를 실행하고 PNG 생성, 960×600 canvas 표시, 제목 변경의 native 상태 반영을 확인한 뒤 자동으로 닫았습니다.
- anywidget 명령 처리는 기능 테스트에 포함됩니다. 실제 Windows JupyterLab 세션은 이번 실행 범위에 포함하지 않았습니다.
- [pytest 출력](results/windows-rtx4070ti-tests.txt) · [Qt 확인 결과](results/windows-rtx4070ti-desktop.json). 로컬 캡처는 `results/images/windows-rtx4070ti/`에 있습니다.

## 재현

```powershell
$env:RUSTUP_TOOLCHAIN = '1.99.0'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[desktop,notebook,benchmark,test]"
.\.venv\Scripts\python.exe benchmarks/compare.py --sizes 100000 1000000 5000000 --kinds line --signals smooth noisy --backends figgy matplotlib-default matplotlib-unsimplified pyqtgraph-default --repeats 5 --timeout 120 --output benchmarks/results/windows-rtx4070ti-line.json
.\.venv\Scripts\python.exe benchmarks/compare.py --sizes 100000 1000000 5000000 --kinds scatter --signals noisy --backends figgy matplotlib-default --repeats 5 --timeout 120 --output benchmarks/results/windows-rtx4070ti-scatter.json
.\.venv\Scripts\python.exe benchmarks/compare.py --sizes 100000 1000000 4000000 --kinds heatmap --backends figgy matplotlib-default --repeats 5 --timeout 120 --output benchmarks/results/windows-rtx4070ti-heatmap.json
.\.venv\Scripts\python.exe benchmarks/plot_results.py benchmarks/results/windows-rtx4070ti-line.json benchmarks/results/windows-rtx4070ti-scatter.json benchmarks/results/windows-rtx4070ti-heatmap.json --output benchmarks/results/windows-rtx4070ti-comparison --subtitle "Windows 11 / RTX 4070 Ti (Vulkan), 5 repeats, 960 x 600 RGBA readback"
```

[선 JSON](results/windows-rtx4070ti-line.json) · [산점도 JSON](results/windows-rtx4070ti-scatter.json) · [히트맵 JSON](results/windows-rtx4070ti-heatmap.json) · [Figgy 비교 차트 SVG (PNG 내장)](results/windows-rtx4070ti-comparison.svg)

![반복 렌더 비교](results/windows-rtx4070ti-comparison.svg)
