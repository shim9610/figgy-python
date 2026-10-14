# figgy-python

NumPy 데이터를 Rust `figgy-renderer 0.16.1`로 그리는 Python 패키지입니다.
0.2의 데스크톱은 **winit + wgpu surface 직접 표시**, Jupyter는 **WASM + 브라우저
WebGPU canvas 직접 표시**를 사용합니다. 차트 모델·설정·피킹·드래그·렌더링은
공통 renderer API이며, Python 저장소에 renderer 소스를 복제하지 않습니다.

## 설치

아직 PyPI에는 게시하지 않았습니다. 소스 설치에는 CPython 3.11~3.14 (3.12 권장),
Rust 1.99 이상과 시스템 컴파일러/링커가 필요합니다. `pip install`이 native 확장을
빌드합니다. WASM은 패키지에 포함하므로 일반 설치에서 별도로 빌드하지 않습니다.

```bash
git clone https://github.com/shim9610/figgy-python.git
cd figgy-python
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
python -m pip install --upgrade pip
python -m pip install ".[notebook]"
python examples/quickstart.py
```

Windows PowerShell 활성화 명령은 `.venv\Scripts\Activate.ps1`입니다. Windows는
MSVC C++ Build Tools, macOS는 Xcode Command Line Tools, Linux는 C/C++ 빌드 도구가
필요합니다. `[desktop]` extra는 기존 설치 명령의 호환성을 위해 빈 extra로 남겼습니다.
**기본 데스크톱 경로에 PySide6/QtWebEngine은 필요 없습니다.**

호환되는 빌드 wheel을 설치하면 Rust가 필요 없습니다. 플랫폼 wheel CI는 구성했으며
이번 실행에서 설치·실행 검증한 wheel은 Linux x86_64 / CPython 3.12용입니다.
Windows·macOS의 새 호스트 실행은 아직 검증하지 않았습니다. Native 그래픽 드라이버는
Windows/DX12, Linux/Vulkan, macOS/Metal이며 upstream Metal은 실험적 지원입니다.

## 데스크톱

바로 편집 창을 열려면 `python examples/desktop_editor.py`를 실행합니다.
[실행 방법·UI 스크린샷·제약](docs/DESKTOP_EDITOR.md)을 함께 확인할 수 있습니다.

```python
import numpy as np
import figgy.pyplot as plt

x = np.linspace(0, 20, 1_000_000)
fig, ax = plt.subplots(backend="native", figsize=(8, 5), dpi=120)
line, = ax.plot(x, np.sin(x), 'b-', label='signal', id='signal')
ax.set_title('One million samples')
ax.set_xlabel('Time (s)')
ax.set_ylabel('Amplitude')
ax.legend()
fig.savefig('signal.png')
plt.show()
```

Rust가 창·이벤트 루프·surface·입력과 선택을 관리합니다. 기존 Figure의 장치와
상주 열을 공유하므로 창을 다시 열 때 데이터를 재업로드하지 않습니다. 서로 다른
native Figure도 프로세스의 하나의 GPU 장치·renderer·column pool을 공유합니다.
각 Figure의 설정과 데이터는 독립적이며, 같은 시리즈 ID를 써도 충돌하지 않습니다.
일반 프레임은
surface에 직접 그리며 RGBA readback·PNG 인코딩·JS 이미지 전달을 수행하지 않습니다.

기본 화면은 차트와 아이콘 툴바이며, 객체를 클릭하면 속성 패널이 열립니다. 제목·축·범례의
글씨 크기·색·폰트 이름, 눈금 글씨 속성, 시리즈 스타일과 히트맵 색 범위를 편집할 수 있습니다. 폰트는 native에서 설치된
family 이름을 사용하며, 없는 이름은 renderer 기본 폰트로 대체됩니다.
Layout은 플롯 영역 이동/크기 조정, 마우스 휠은 줌입니다. **Copy Python**은 현재 SSOT를
`fig.apply_settings(...)` 코드로 복사하며, **Save PNG**는 입력한 경로에 저장합니다.
추가 renderer 속성은 Advanced settings의 JSON에서 편집할 수 있습니다.

`show()`는 main thread에서 모든 열린 Figgy 창이 닫힐 때까지 실행합니다.
`show(block=False)` 뒤에는 main thread에서 이벤트를 계속 처리해야 합니다.

```python
from figgy.desktop import poll_events, run_events
window = fig.show(block=False)
# 다른 main-thread 루프에 통합한다면 poll_events()를 자주 호출합니다.
run_events()                    # 모든 현재 창이 닫힐 때까지 실행
```

이벤트 펌프와 native GPU 작업은 GIL을 해제합니다. 여러 Figure를 각각 비차단 모드로
연 뒤 같은 이벤트 루프에서 처리할 수 있습니다. `fig.close()`로 native 자원을 해제합니다.
Qt/Tk의 외부 루프나 `%gui qt`에 자동 통합하지 않습니다.

첫 native Figure의 `pool_bytes`가 공유 pool의 초기 크기를 정합니다. 이후 Figure의
할당도 같은 pool을 사용하므로 합계 데이터가 adapter의 한 storage buffer 한도를
넘으면 `MemoryError`가 납니다. 활성 데이터를 자동으로 버리거나 스트림으로 바꾸지
않습니다. `fig.close()`는 해당 데이터 공간을 반납하지만 공유 pool 용량·파이프라인은
다음 Figure를 위해 유지합니다. 모든 native Figure를 닫은 뒤 `figgy.release_gpu()`로
공유 자원까지 해제할 수 있습니다. Jupyter의 브라우저 pool은 여전히 뷰별로 독립적입니다.

```python
ax.set_title("Title", color="red", fontsize=20, font="DejaVu Serif")
fig.update("tick_labels_bottom", fontsize=12, font="DejaVu Serif", color="blue")
```

## 명시적 GPU 준비

그리기 전에 준비 시간을 따로 처리하려면 Figure의 사전 준비 API를 사용합니다.

```python
fig, ax = plt.subplots(backend="native")
ax.plot(x, y)
report = fig.prepare()          # resident 파이프라인 준비 + 현재 차트 1회 실행
print(report["elapsed_ms"])
fig.show()
```

Jupyter에서는 위젯을 먼저 표시한 뒤 명시적으로 GPU 준비를 시작할 수 있습니다.

```python
fig, ax = figgy.subplots(backend="webgpu")
ax.plot(x, y)
display(fig.widget(auto_prepare=False))  # 아직 브라우저 GPU를 초기화하지 않음
report = await fig.prepare_async()      # 초기화·바이너리 업로드·사전 준비
```

이 준비는 현재 Figure/브라우저 뷰의 GPU 리소스를 유지하는 방식입니다. PNG를
생성하지 않습니다. Native는 완료 확인을 위해 현재 차트를 RGBA로 한 번 읽으며,
일반 표시 프레임의 readback 경로에는 변화가 없습니다. 기본 Jupyter 표시는 이전처럼
자동 초기화합니다. 위젯을 생성한 뒤에는 데이터 추가가 잠기므로 시리즈를 먼저 만듭니다.

**pip 설치 때 GPU 셰이더를 미리 컴파일하거나 캐시 파일을 저장하는 기능은 아닙니다.**
renderer 0.16.1에는 영속 파이프라인 캐시를 연결하는 공개 API가 없습니다.
준비 후에도 surface 포맷 변경, 새 스타일/데이터 종류, 드라이버 내부의 지연 컴파일은
추가 준비 비용을 만들 수 있습니다. `python -m figgy.prepare --json`은 로컬 GPU 준비
진단용이며, 종료 후 다음 프로세스의 컴파일 생략을 보장하지 않습니다. 자세한 범위는
[GPU 준비 문서](docs/PREPARATION.md)를 참고하세요.

## Jupyter

```bash
python -m pip install jupyterlab ".[notebook]"
jupyter lab examples/interactive.ipynb
```

```python
import numpy as np
import figgy

fig, ax = figgy.subplots(backend="webgpu")
x = np.linspace(0, 20, 100_000, dtype=np.float32)
ax.plot(x, np.sin(x), id="signal")
ax.set_title("Edit in the browser")
display(fig)
```

`backend="auto"`는 IPython 커널에서 `webgpu`, 그 외에서 `native`를 선택합니다.
WebGPU Figure 생성은 커널의 GPU를 초기화하지 않습니다. NumPy 스냅샷을 바이너리
버퍼로 전송하고, upstream WASM이 별도 브라우저 GPU에 상주 데이터를 업로드합니다.
초기 전송 이후 줌·피킹·드래그·스타일 편집은 브라우저에서 처리합니다. 드래그 중 매
포인터 이동마다 커널에 요청하지 않으며, 일반 redraw에 PNG 생성·전송이 없습니다.

편집 설정은 revision으로 동기화합니다. Python은 마지막으로 승인된 설정을 읽으며,
대기 중인 브라우저 편집까지 반영하려면 다음 셀에서 동기화를 기다립니다.

```python
await fig.sync()
print(fig.get_settings())
print(fig.to_code())
await fig.savefig_async("edited.png", dpi=240)
png_bytes = await fig.to_png_async()
```

브라우저 PNG 저장은 비동기입니다. 동기 `savefig()`/`render_rgba()`는 native 전용입니다.
Copy Python은 원본 배열을 포함하지 않으며, 같은 시리즈 ID/열 연결을 가진 Figure에
붙여 넣습니다. Browser Save PNG도 현재 편집된 renderer 문서를 내보냅니다.

커널·JS·WASM·GPU 메모리는 별개이며 초기 복사와 전송 비용이 있습니다. zero-copy가
아닙니다. 기본적으로 업로드 성공 뒤 임시 전송 스냅샷을 해제하고, 표시 후 데이터 열
추가는 막습니다. 새 데이터를 그릴 때는 Figure를 새로 만드세요. 브라우저 새로고침이나
여러 view에 다시 표시하려면 셀을 다시 실행하거나 생성 시
`retain_notebook_data=True`로 전송 버퍼를 보관합니다. Native에는 원본 배열의 영구
CPU 사본을 추가하지 않습니다.

WebGPU에는 지원 브라우저와 HTTPS/localhost가 필요합니다. 미지원/초기화 실패는 출력에
명확히 표시하며 자동 fallback을 하지 않습니다. 커널 GPU를 쓸 수 있을 때만 명시적으로
`Figure(backend="native").widget(backend="png")`를 사용할 수 있습니다. 이 경로에는
**Kernel PNG fallback** 표시가 있고 이미지 전송이 발생합니다.

WASM/JS는 wheel에 포함됩니다. 개발 서버나 외부 자산 CDN이 필요 없습니다. 원격 커널이면
Jupyter 서버 환경에도 widget/anywidget frontend extension을 설치해야 합니다.

## 데이터·지원 범위

`plot`, `scatter`, `imshow`, 한 패널의 여러 시리즈, 제목·축·범례·범위·그리드,
SSOT 설정 읽기·교체와 PNG를 지원합니다. matplotlib 전체 API 호환 계층은 아닙니다.
다중 패널과 추가 차트의 고수준 API는 아직 없습니다.

`figsize`는 inch, `linewidth`/`markersize`/`fontsize`는 point, scatter `s`는 point²입니다.
contiguous f32/f64 native 업로드는 기존 hi/lo staging 경로를 유지하며, strided 입력은
contiguous 복사, 정수 입력은 float64 정규화합니다. 이후 원본 배열 변경은 그림에
반영하지 않습니다. Native 초기 `pool_bytes`는 최종 한도가 아니며 부족하면 확장합니다.
브라우저는 upstream의 초기 16 MiB 풀을 확장합니다.

**자동 다운샘플링·스트리밍·청크 렌더 전환은 없습니다.** 전체 데이터를 할당해 그리며
할당/디바이스 한도 실패는 예외 또는 브라우저 오류로 전달합니다. Native `MemoryError`는
열 ID, 요청 바이트, 풀 사용량/용량, 디바이스 한도와 어댑터 정보를 포함합니다.
`fig.info`는 계측 범위의 GPU 메모리·업로드/readback/PNG 횟수를 보여줍니다.
실제 VRAM이나 드라이버 내부 사용량 전체 측정치는 아닙니다.

## 성능·검증

기존 [Windows GPU 결과](benchmarks/WINDOWS_GPU_RESULTS.md)는 완료된 RGBA readback
측정입니다. 새 surface의 화면 표시 FPS나 입력 지연 검증 결과로 재해석하지 않습니다.
보고용 비교 그래프도 Figgy로 그립니다.

```bash
python -m pip install ".[benchmark]"
python benchmarks/compare.py --sizes 100000 1000000 5000000 --kinds line scatter \
  --signals smooth noisy --repeats 3 --output benchmarks/results/my-machine.json
python benchmarks/ui_surface.py --points 100000 --frames 120
```

`ui_surface.py`는 readback 없는 surface 제출률을 별도로 측정합니다. 실제 모니터 FPS나
입력부터 화면 광출력까지의 지연 측정은 아닙니다. 클라우드 소프트웨어 GPU 수치와 실제
Windows 하드웨어 수치를 구분합니다.

검증 방법·수명·플랫폼 제약은 [호스트 구조](docs/HOSTS.md), 이번 실행 결과는
[호스트 검증 기록](docs/HOST_VALIDATION.md)에 있습니다. WASM 재빌드는 maintainer용
`scripts/build-wasm.sh`이며 upstream 버전과 자산 해시를 기록합니다.

클라우드 도구 준비는 기존 `scripts/setup-cloud.sh`와
`source /workspace/.figgy-tools/activate.sh`를 사용합니다.
