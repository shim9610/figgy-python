# Python 바인딩 구현·벤치마크 결과

Windows/RTX 4070 Ti의 실제 GPU 측정은 [Windows 벤치마크](WINDOWS_RESULTS.md)에 별도로 기록했습니다.

fastplotlib·VisPy·실제 pyqtgraph OpenGL 경로를 포함한 후속 결과는 [Windows GPU 비교](WINDOWS_GPU_RESULTS.md)를 참고합니다.

보고용 비교 차트도 Figgy로 렌더합니다. 한 패널씩 그린 결과를 이미지로 배치하며,
SVG는 Figgy가 렌더한 PNG를 내장한 형식입니다.

현재 구현은 figgy-renderer 0.16.1을 재사용하는 Python 0.1 알파입니다.
matplotlib 형태의 plot/scatter/imshow API, NumPy 직접 staging 업로드, 동일 설정 경로를
쓰는 데스크톱·Jupyter 내부 편집, Python 설정 코드 복사, PNG 저장을 구현했습니다.
자동 스트림·다운샘플링·청크 렌더 전환은 없습니다. 작은 상주 풀을 필요에 따라 확장하고,
디바이스 한도 초과는 용량·열 이름·어댑터를 포함한 MemoryError로 반환합니다.

## 실행 조건

- Python 3.12.14, NumPy 2.5.4, matplotlib 3.11.2, pyqtgraph 0.14.0, PySide6 6.12.0.
- Linux x86_64, llvmpipe LLVM 19.1.7 **CPU Vulkan**, CPU quota 4 cores. 물리 GPU 없음.
- 960×600 완료된 RGBA readback. 선 두께 2.5 px, scatter 지름 5 px.
- 같은 float64 입력. 선은 매끄러운 파형과 고정 seed의 잡음 파형을 분리.
- matplotlib와 Figgy의 실제 plot 영역을 맞춤. 히트맵은 양쪽에 colorbar를 포함.
  pyqtgraph plot 영역은 QGraphicsItem 경계 때문에 너비·높이에 0.5 px 차이가 있음.
- Figgy는 sample count 1 + shader AA. matplotlib는 Agg AA, pyqtgraph 기본 QPainter는
  AA off / OpenGL off / autoDownsample off. 이미지를 동일한 픽셀로 만드는 비교는 아님.
- 독립 worker에서 초기화·등록/fit·첫 draw·반복 draw·축/스타일 편집·PNG를 구분.
  반복 draw는 3회 중앙값. import와 데이터 생성은 시간 합계에서 제외.
- process는 새로 만들지만 OS/font/Mesa shader cache는 지우지 않음. 완전한 cold-cache
  측정이나 화면 표시 FPS 측정이 아님. PNG·Jupyter comm·브라우저 표시 지연은 별도.
- 전체 worker peak RSS에는 입력과 각 라이브러리/드라이버의 메모리가 포함되며,
  물리 VRAM이나 순수 Rust/Python 객체 메모리 비교가 아님.

## 측정에서 보이는 차이

400만 셀 히트맵 반복 렌더는 Figgy 27.5 ms,
matplotlib 124.3 ms로 약
**4.5배** 차이였습니다.
하지만 첫 결과까지는 Figgy 601 ms,
matplotlib 180 ms로 matplotlib가 빨랐습니다.
상주 행렬을 재사용하는 반복 편집·렌더 경로에서 이점이 나타났습니다.

100만 점 잡음 선은 Figgy 650 ms,
matplotlib 단순화 해제 2696 ms로 약
4.1배 차이였습니다.
matplotlib **기본 단순화 설정은 이보다 빠릅니다**. 매끄러운 선에서는 기본/단순화 해제
모두 Figgy보다 빨랐고, 산점도는 대체로 비슷했습니다. Rust라서 모든 작업이 빨라진다는
결론은 이 결과로 뒷받침되지 않습니다.

500만 점 잡음 선에서 matplotlib 단순화 해제는 Agg cell block 한도 오류가 발생했습니다.
이를 timeout/메모리 부족/속도 수치로 바꾸지 않고 원문 오류를 JSON에 보존했습니다.
기본 matplotlib와 Figgy, pyqtgraph는 같은 입력을 완료했습니다.

이 문서의 측정은 소프트웨어 Vulkan 결과입니다. 물리 GPU에서 같은 스크립트를 실행한
Windows/RTX 4070 Ti/Vulkan 결과는 [Windows 벤치마크](WINDOWS_RESULTS.md)를 참고합니다.
Windows/DX12와 macOS/Metal 측정은 별도로 필요합니다.

## line

| 입력 | 백엔드 | 초기화+등록/fit+첫 draw (ms) | 반복 draw (ms) | 축 변경+draw (ms) | Peak RSS (MiB) |
|---|---|---:|---:|---:|---:|
| 100,000 / smooth | figgy | 277.7 | 73.8 | 83.3 | 226.5 |
| 100,000 / smooth | matplotlib-default | 45.1 | 22.8 | 24.6 | 78.0 |
| 100,000 / smooth | matplotlib-unsimplified | 51.2 | 28.5 | 28.9 | 78.1 |
| 100,000 / smooth | pyqtgraph-default | 133.5 | 44.7 | 47.7 | 132.5 |
| 1,000,000 / smooth | figgy | 797.5 | 474.1 | 465.3 | 293.8 |
| 1,000,000 / smooth | matplotlib-default | 118.2 | 57.8 | 54.7 | 136.6 |
| 1,000,000 / smooth | matplotlib-unsimplified | 216.7 | 160.1 | 159.7 | 140.9 |
| 1,000,000 / smooth | pyqtgraph-default | 1036.5 | 429.6 | 426.2 | 174.0 |
| 5,000,000 / smooth | figgy | 3396.1 | 2433.8 | 2728.6 | 471.0 |
| 5,000,000 / smooth | matplotlib-default | 455.2 | 231.4 | 224.4 | 401.4 |
| 5,000,000 / smooth | matplotlib-unsimplified | 916.8 | 738.9 | 755.0 | 419.1 |
| 5,000,000 / smooth | pyqtgraph-default | 4738.3 | 2119.0 | 1988.8 | 353.9 |
| 100,000 / noisy | figgy | 301.6 | 103.5 | 97.0 | 230.5 |
| 100,000 / noisy | matplotlib-default | 136.0 | 102.9 | 111.1 | 119.6 |
| 100,000 / noisy | matplotlib-unsimplified | 259.1 | 259.0 | 237.2 | 167.9 |
| 100,000 / noisy | pyqtgraph-default | 193.5 | 83.0 | 90.8 | 135.9 |
| 1,000,000 / noisy | figgy | 886.8 | 650.0 | 647.5 | 410.7 |
| 1,000,000 / noisy | matplotlib-default | 232.2 | 175.6 | 191.7 | 181.1 |
| 1,000,000 / noisy | matplotlib-unsimplified | 2995.3 | 2695.7 | 2610.2 | 983.2 |
| 1,000,000 / noisy | pyqtgraph-default | 1378.7 | 640.1 | 623.5 | 176.9 |
| 5,000,000 / noisy | figgy | 5000.2 | 4756.4 | 4484.2 | 2276.5 |
| 5,000,000 / noisy | matplotlib-default | 881.0 | 389.9 | 437.5 | 402.3 |
| 5,000,000 / noisy | matplotlib-unsimplified | Agg 오류 | — | — | — |
| 5,000,000 / noisy | pyqtgraph-default | 6789.0 | 2976.8 | 3089.2 | 357.8 |

## scatter

| 입력 | 백엔드 | 초기화+등록/fit+첫 draw (ms) | 반복 draw (ms) | 축 변경+draw (ms) | Peak RSS (MiB) |
|---|---|---:|---:|---:|---:|
| 100,000 / noisy | figgy | 307.6 | 52.8 | 51.9 | 172.1 |
| 100,000 / noisy | matplotlib-default | 65.9 | 44.6 | 43.1 | 78.1 |
| 1,000,000 / noisy | figgy | 617.3 | 366.0 | 355.6 | 302.3 |
| 1,000,000 / noisy | matplotlib-default | 364.2 | 333.5 | 339.7 | 135.6 |
| 5,000,000 / noisy | figgy | 2074.2 | 1603.7 | 1624.1 | 619.5 |
| 5,000,000 / noisy | matplotlib-default | 1844.0 | 1720.7 | 1603.0 | 401.4 |

## heatmap

| 입력 | 백엔드 | 초기화+등록/fit+첫 draw (ms) | 반복 draw (ms) | 축 변경+draw (ms) | Peak RSS (MiB) |
|---|---|---:|---:|---:|---:|
| 99,856 / smooth | figgy | 296.6 | 24.1 | 26.7 | 158.3 |
| 99,856 / smooth | matplotlib-default | 70.3 | 40.1 | 39.5 | 104.6 |
| 1,000,000 / smooth | figgy | 343.4 | 22.4 | 21.8 | 167.9 |
| 1,000,000 / smooth | matplotlib-default | 84.6 | 48.8 | 48.8 | 173.3 |
| 4,000,000 / smooth | figgy | 601.1 | 27.5 | 24.4 | 240.3 |
| 4,000,000 / smooth | matplotlib-default | 179.5 | 124.3 | 126.9 | 407.2 |

## 기능·배포 검증

- 설치한 release wheel에서 pytest **10건 통과**. source 배열 변경 독립성,
  업로드 재사용, 설정 코드 재현과 이미지 일치, stale/잘못된 설정 거부,
  PNG 배율, 행렬 선택, widget 편집, 상주 풀 확장, 실제 디바이스 한도 오류를 확인.
- Chromium에서 실제 공통 ES module + native renderer를 연결하여 제목 편집,
  클릭/드래그, 클립보드 코드 복사, PNG 다운로드를 확인.
- 실제 JupyterLab 4.6.4 + kernel + anywidget에서 제목·색상 편집, Python 복사와
  PNG 다운로드 확인. 해당 브라우저 실행에서 page error 없음.
- QtWebEngine 데스크톱 창도 headless/offscreen 환경에서 실행하고 화면 확인.
- Linux CPython 3.12 / glibc 2.35 이상 wheel 생성 및 twine check --strict 통과.
- Windows/macOS와 Python 3.11~3.14 wheel CI를 구성했으나 원격 실행은 아직 없음.
- Windows 실제 Qt GUI와 물리 GPU 검증은 [별도 결과](WINDOWS_RESULTS.md)에 기록함.
- PyPI 게시와 실제 macOS GUI 검증은 아직 수행하지 않음.
  upstream renderer가 macOS/Metal을 실험적 지원으로 명시함.

한 패널의 plot/scatter/imshow가 현재 고수준 Python API입니다. 다중 패널과
pie/bar/boxplot/contour 고수준 API는 이후 범위입니다. 원본 데이터 값 드래그 편집은
없으며 현재 편집은 외형·배치·축 설정을 다룹니다.

## 재현

```bash
python -m pip install '.[benchmark]'
python benchmarks/compare.py --sizes 100000 1000000 5000000   --kinds line --signals smooth noisy   --backends figgy matplotlib-default matplotlib-unsimplified pyqtgraph-default   --repeats 3 --timeout 90 --output benchmarks/results/my-line.json
python benchmarks/compare.py --sizes 100000 1000000 5000000   --kinds scatter --signals noisy --backends figgy matplotlib-default   --repeats 3 --output benchmarks/results/my-scatter.json
python benchmarks/compare.py --sizes 100000 1000000 4000000   --kinds heatmap --backends figgy matplotlib-default   --repeats 3 --output benchmarks/results/my-heatmap.json
```

[선 원자료](results/llvmpipe-line.json) · [산점도 원자료](results/llvmpipe-scatter.json) ·
[히트맵 원자료](results/llvmpipe-heatmap.json) · [비교 차트 SVG](results/comparison.svg)
