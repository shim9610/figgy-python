# figgy-python

matplotlib에 익숙한 Python API로 Rust `figgy-renderer`를 사용하는 초기 래퍼입니다.
NumPy 데이터 입력, 창/노트북 UI, 설정 코드 생성, 배포와 벤치마크는 이 저장소가
소유합니다. 차트 모델·배치·선택 판정·드래그·렌더링은 renderer의 공개 API를 씁니다.
렌더러 소스를 복제하지 않으며 crates.io **0.16.1**을 Cargo.lock으로 고정합니다.

## 설치

현재 PyPI에는 게시하지 않았습니다. 저장소를 받은 뒤 아래 명령으로 설치하면
Python에서 사용할 수 있습니다. 소스 설치에는 **CPython 3.11~3.14 (3.12 권장),
Rust 1.99 이상과 시스템 컴파일러/링커**가 필요합니다. `pip install`이 Rust 확장을
빌드하므로 별도 `cargo build`는 필요 없습니다. 첫 설치는 의존성을 받아 빌드합니다.

```bash
git clone https://github.com/shim9610/figgy-python.git
cd figgy-python
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
python -m pip install --upgrade pip
python -m pip install ".[desktop,notebook]"
python examples/quickstart.py
```

Windows PowerShell에서는 활성화 명령을 `.venv\Scripts\Activate.ps1`로 바꿉니다.
Windows는 MSVC Build Tools의 C++ 개발 도구, macOS는 Xcode Command Line Tools,
Linux는 C/C++ 빌드 도구가 필요합니다. 렌더링에는 사용할 수 있는 그래픽 드라이버
(Windows/Vulkan·DX12, Linux/Vulkan, macOS/Metal)가 필요합니다. macOS/Metal은 upstream에서
실험적 지원입니다. 실제 실행 검증은 Linux와 Windows에서 완료했으며,
Windows/RTX 4070 Ti의 Vulkan 실행 결과는 [Windows 벤치마크](benchmarks/WINDOWS_RESULTS.md)에 기록했습니다.

예제는 `signal.png`를 저장하고 객체를 선택·편집할 수 있는 창을 엽니다.
노트북을 실행할 환경이 없다면 아래 명령으로 JupyterLab을 설치하고 예제를 엽니다.

```bash
python -m pip install jupyterlab
jupyter lab examples/interactive.ipynb
```

기본 의존성은 NumPy입니다. `[desktop]`은 PySide6/QtWebEngine 창,
`[notebook]`은 anywidget/ipywidgets를 설치합니다. PNG 저장만 할 때는 GUI가 필요
없습니다. 이후 코드를 변경했다면 `python -m pip install ".[desktop,notebook]"`을
다시 실행해 설치본과 Rust 확장을 갱신합니다.

빌드된 wheel은 저장소에 커밋하지 않습니다. GitHub Actions의 플랫폼 wheel 빌드가
성공하면 해당 실행의 Artifacts에서 내려받을 수 있으며, 호환되는 wheel 설치에는
Rust가 필요 없습니다. 로컬에서 검증한 wheel은 Linux x86_64 / CPython 3.12 /
glibc 2.35 이상용입니다. 플랫폼 CI 구성과 실제 검증 완료는 구분합니다.

클라우드 개발 환경을 다시 준비할 때는 `bash scripts/setup-cloud.sh`와
`source /workspace/.figgy-tools/activate.sh`를 사용합니다. 이 스크립트는
`/workspace`의 Debian 기반 개발 환경 전용이며 일반 로컬 설치에는 필요 없습니다.

## 사용법

```python
import numpy as np
import figgy.pyplot as plt

x = np.linspace(0, 20, 1_000_000)
fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
line, = ax.plot(x, np.sin(x), 'b-', label='signal', id='signal')
ax.set_title('One million samples')
ax.set_xlabel('Time (s)')
ax.set_ylabel('Amplitude')
ax.legend()

fig.savefig('signal.png')
plt.show()             # 닫을 때까지 실행하는 별도 편집 창
```

노트북에서는 같은 Figure를 셀 안에서 선택하고 편집합니다.

```python
display(fig)           # 기본 표현도 편집 가능한 widget
# 또는 display(fig.widget())
```

창과 노트북은 같은 ES module 편집기를 사용합니다. 그림에서 객체를 클릭하거나
Object 목록에서 고르고, 속성 패널을 수정합니다. 제목·축 제목·라벨·범례를 드래그할
수 있으며 Edit plot area를 켜면 영역과 리사이즈 핸들을 편집합니다. 데이터 객체
선택은 Rust GPU picker를 사용합니다. 선택된 데이터에는 renderer의 강조 표시를
사용하고, 편집 핸들은 UI가 덧그려 PNG에는 포함하지 않습니다.

**Copy Python**은 현재 설정을 실행 가능한 `fig.apply_settings(...)` 코드로 복사합니다.
원본 배열은 코드에 포함하지 않습니다. 같은 시리즈 ID와 열 연결로 Figure를 생성한
뒤 붙여 넣습니다. **Save PNG**는 현재 편집 결과를 다운로드/저장합니다.

```python
line.set_color('#d62728')
line.set_linewidth(2.5)
fig.update('chart_title', text='Edited result', offset=(12, -4))
fig.savefig('edited.png', dpi=240)
print(fig.to_code())
fig.close()            # native resources와 연결된 UI 해제
```

## 현재 지원 범위

- `Figure`, `Axes`, `Artist`, `subplots()`와 작은 `figgy.pyplot` 인터페이스.
- `plot`, `scatter`, `imshow`; 한 Figure의 여러 시리즈와 한 패널.
- `figsize`는 inch, `dpi`는 논리 캔버스 해상도입니다. `linewidth`, `markersize`, `fontsize`는
  point, scatter의 `s`는 point²이며 native pixel/radius로 변환합니다.
- 제목·축 제목·범례·축 범위·그리드, 선/점 스타일, renderer 색상표.
- `set_xscale('log')`, `set_yscale('log')`와 선형 축 복원. 로그 축으로 바꾸기 전에
  `set_xlim`/`set_ylim`으로 양수 범위를 설정합니다.
- SSOT 전체 설정 읽기·교체, 안정적인 대상 ID 편집, 배치 이동·크기 조정.
- PNG bytes, `savefig`, 완료된 RGBA readback.
- anywidget 노트북 내부 편집과 QtWebEngine 데스크톱 창.

matplotlib 전체 API 호환 계층은 아닙니다. 다중 패널, pie/bar/boxplot/contour의 고수준
Python API, 원본 데이터 값을 드래그로 수정하는 편집기는 아직 없습니다.
Rust에서 지원하는 모든 차트가 Python에 자동 노출되는 것은 아닙니다.
raw settings의 나머지 renderer 필드는 읽고 편집할 수 있습니다.

`show()`는 main thread에서 호출합니다. `show(block=False)`는 창을 반환하며
호출자가 Qt event loop를 실행하거나 IPython의 Qt 통합을 사용합니다.

## 데이터와 할당

**자동 스트림 전환, 다운샘플링, 청크 렌더링을 넣지 않습니다.** 요청한 전체 데이터를
상주 열로 할당하고 그립니다. 기본 8 MiB 풀은 공간이 부족하면 renderer의 메모리
확장 경로를 사용하며, 디바이스 한도나 실제 할당 실패는 호출자에게 예외로 돌아갑니다.
`pool_bytes`는 초기 용량이며 인위적인 최종 제한이 아닙니다.

contiguous float32/float64 NumPy 입력을 Rust에서 빌려 GPU staging에 바로 인코딩합니다.
Python list나 임시 Rust Vec를 만들지 않습니다. strided 입력은 contiguous로 복사하고,
정수/기타 실수 입력은 float64로 정규화합니다. float64는 renderer의 hi/lo 경로를 씁니다.
GPU 전송 자체는 복사가 있으므로 GPU zero-copy를 의미하지 않습니다.

입력은 업로드 당시의 스냅샷입니다. 이후 원본 NumPy 배열을 수정해도 그림은 바뀌지
않습니다. 창/노트북 redraw·축 변경·속성 편집은 상주 데이터를 재사용합니다. 원본
배열의 CPU 사본을 래퍼가 추가로 보관하지 않습니다. 초기화·GPU fit·렌더링·피킹에서는
GIL을 해제하고, NumPy를 빌린 업로드 구간에서는 GIL을 유지합니다.

할당/한도 실패는 예를 들어 아래 정보를 포함한 `MemoryError`를 반환합니다.

```text
upload failed: column="series_1/x", values=16777217,
requested_gpu_bytes=134217736, pool_used_bytes=..., pool_capacity_bytes=...,
adapter_column_pool_limit_bytes=134217728, adapter="llvmpipe (...)";
... exceeds GPU buffer limit ...
```

`fig.info`에서 어댑터, 현재 풀/사용량, 열 업로드 횟수, 알려진 GPU 할당량을 확인합니다.
`known_gpu_bytes`는 호스트 texture/readback과 renderer의 계측 범위를 합한 값이며
드라이버·셰이더 내부 사용량이나 실제 VRAM 점유 측정치는 아닙니다.

## 렌더 경로와 성능

기본 크기에서는 축 texture, 출력 texture, readback buffer를 재사용하며 등록된
시리즈의 native style cache를 씁니다. 매 호출마다 실제 GPU draw와 완료된 readback을
수행합니다. 출력 이미지를 재사용해서 벤치마크를 빠르게 만들지 않습니다.
UI만 같은 revision의 PNG를 재사용하고 포인터 이벤트를 합쳐 전송량을 줄입니다.

화면 크기 렌더는 sample count 1과 renderer의 shader AA를 사용합니다. `scale != 1`
export는 renderer의 표준 export 경로로 처리하므로 MSAA 경계 픽셀이 달라질 수 있습니다.
데스크톱과 노트북 UI는 PNG를 전달하므로 커널 통신/PNG encoding/브라우저 표시 지연은
native RGBA 벤치마크에 추가됩니다. 이는 GPU surface 직접 표시의 FPS 측정이 아닙니다.

벤치마크는 초기화, 데이터 등록/fit, 첫 draw, 반복 draw, 축/스타일 편집, PNG 저장,
worker 전체 peak RSS를 분리합니다. 입력 생성과 import는 타이밍에서 제외하며 각
백엔드를 독립 프로세스에서 실행합니다. matplotlib 기본 단순화와 단순화 해제 결과를
분리하고, pyqtgraph OpenGL 표시와 QPainter/AA 설정도 구분합니다. 실패/timeout 행을 보존합니다.

```bash
python -m pip install '.[benchmark,benchmark-gpu]'
python benchmarks/compare.py --sizes 100000 1000000 5000000 \
  --kinds line scatter --signals smooth noisy --repeats 3 \
  --output benchmarks/results/my-machine.json
```

어댑터/드라이버와 버전을 JSON에 기록합니다. 현재 클라우드 결과는 **llvmpipe CPU
Vulkan, CPU quota 4 cores**이며 물리 GPU 성능을 입증하지 않습니다. 같은 스크립트를
Windows/DX12, macOS/Metal, Linux/Vulkan의 실제 하드웨어에서 실행할 수 있습니다.
렌더러가 macOS/Metal을 실험적 지원으로 명시하므로 해당 검증은 별도로 필요합니다.

기본 비교에는 fastplotlib, VisPy와 `useOpenGL=True`의 실제 pyqtgraph OpenGL 렌더를
포함합니다. GPU 좌표 정밀도와 AA 방식은 라이브러리마다 다르며, Windows의 확장 비교는
[GPU 라이브러리 벤치마크](benchmarks/WINDOWS_GPU_RESULTS.md)에 기록했습니다.

`benchmarks/plot_results.py`는 결과 JSON의 비교 그래프도 Figgy로 렌더합니다.
현재 한 패널 API로 네 차트를 각각 그린 뒤 완성된 이미지를 배치하며, PNG와
PNG를 내장한 SVG를 저장합니다. 그래프를 그리는 데 matplotlib를 사용하지 않습니다.

## 검증과 wheel

```bash
python -m venv .venv
# 환경에 맞게 .venv 활성화
python -m pip install maturin '.[test]'
maturin develop --release --locked
python -m pytest -q
cargo fmt --check
maturin build --release --locked --out dist
python -m twine check --strict dist/*
```

브라우저 통합 검사는 추가로 Playwright/Chromium이 필요합니다. `BROWSER_EXECUTABLE_PATH`로
실행 파일을 지정할 수 있습니다. native GPU 초기화 실패를 기능 검사 통과로 처리하지
않습니다. macOS/Windows/Python 3.11~3.14 wheel CI는 구성했으며 원격 실행 결과는 아직
없습니다. 자동 PyPI publish 단계는 포함하지 않습니다.
