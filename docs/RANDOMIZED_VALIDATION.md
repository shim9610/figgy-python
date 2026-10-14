# 무작위 입력·상태·동시성 검증

2026-10-14, Linux x86_64에서 공개 `figgy-renderer 0.16.1`을 사용했습니다.
Native는 Vulkan llvmpipe 소프트웨어 GPU, notebook은 실제 JupyterLab + headed
Chromium + SwiftShader WebGPU입니다. Windows/macOS 하드웨어 결과가 아닙니다.

## 오래 걸린 사례의 실제 원인

[업스트림 이슈 #6](https://github.com/shim9610/figgy/issues/6)에 GPU 없는 Rust
최소 재현 코드와 native stack/CPU 사용량 근거를 등록했습니다. 재현 코드는
[scripts/repro_upstream_colorbar](../scripts/repro_upstream_colorbar/)에 있습니다.

`chart_title.top_margin = -1e38`인 히트맵 설정을 upstream `Config::validate()`가
허용합니다. 320×240 canvas의 `data_area()` 높이가 `u32::MAX`로 포화되고,
`draw_colorbar_strip()`가 약 43억 개의 밴드를 CPU에서 그리려고 합니다.
25/50/75/100초의 native stack은 축·장식 CPU raster의 사각형 그리기에 있었고,
CPU user time은 계속 증가했으며 GPU 스레드는 대기 중이었습니다. 110초에
외부 테스트 watchdog으로 종료했습니다. 이는 유한하지만 비정상적으로 큰 CPU
루프이며, GPU 제출/readback 교착이라는 앞선 설명은 잘못됐습니다.

운영 코드에는 **30초 제출 제한·1초 readback 제한이 없습니다**. 기존 renderer의
GPU 완료 대기와 mapping callback 대기를 유지합니다. 정상적으로 오래 걸리는
렌더링을 임의의 시간으로 중단하지 않습니다. notebook의 사용자가 조절하는
`prepare_async(timeout=...)` 등의 comm 응답 제한은 별개이며, 타임아웃이 발생해도
브라우저 렌더링을 강제 중단하지 않습니다.

Upstream 수정 전에는 설정 commit 전에 음수 제목 여백을 `ValueError`로 거부하고,
공통 모델의 `Config::validate()`로 다른 레이아웃 규칙도 검사합니다. 제목을 위로
옮기려면 `offset_y`를 사용합니다. 글꼴·선 두께에 임의의 8192px 상한을 추가하지
않습니다. 기존 canvas 크기 제한은 유지합니다.

## 무작위 검증 방법과 결과

`scripts/check_randomized.py`는 seed를 고정하고 다음을 생성합니다.

- 중첩 SSOT 트리 전체의 임의 노드 변경·삭제·알 수 없는 필드 추가.
- NaN/Inf, 큰 수·아주 작은 수, Unicode/NUL, 잘못된 타입과 차원의 배열,
  비연속 배열, 여러 dtype, 잘못된 API 인자·ID·backend.
- 생성·추가·편집·fit·범위·선택·드래그·직렬화·닫기·재생성의 임의 순서.
- 네 스레드에서 공유 Figure 읽기/편집/render와 다른 Figure 생성/닫기를 혼합.

각 worker를 별도 프로세스로 실행합니다. watchdog 초과 시 스택·마지막 호출·seed를
보존하고 실패로 기록합니다. **watchdog 초과만으로 교착이나 GPU 결함이라고
판정하지 않습니다.** 테스트의 배열 크기와 canvas 표시 작업은 자원 사용을
제한하며, 이것은 제품의 다운샘플링·스트리밍 정책이 아닙니다.

Native와 GPU 없는 notebook 모델에 대해 seed 0–31을 사용했습니다. 128개의
순차 worker × 500회와 64개의 동시성 worker × 4스레드 × 500회로 **192,000회**를
실행했습니다. 192개 프로세스 모두 완료했고 watchdog 초과는 0회였습니다.
가장 오래 걸린 worker는 17.501초였습니다. [집계 JSON](../reports/randomized-model.json).

| 결과 | 호출 수 |
|---|---:|
| 정상 처리 | 58,193 |
| ValueError | 100,666 |
| TypeError | 23,493 |
| RuntimeError | 9,501 |
| OverflowError | 147 |

거부된 순차 호출은 설정·revision·컬럼 개수/바이트·다음 ID가 보존되는지 검사합니다.
허용된 설정은 다시 적용 가능한지 확인합니다. 별도 sentinel Figure의 설정과 native
RGBA 결과도 보존되는지 확인했습니다. 256개 작업 스레드가 종료했고, 128개 순차
worker에서 오류 뒤 정상 동작 복구를 확인했습니다. 완료 RGBA 확인은 표시 FPS나
입력 지연 측정이 아닙니다.

## 발견하고 수정한 다른 문제

- 실패한 `imshow()`가 colorbar/축 설정을 먼저 바꾸던 문제: 업로드·시리즈 등록·fit·
  히트맵 범위 적용을 문서 transaction으로 묶고 실패 시 컬럼·설정·revision을 복구.
- 유한한 JSON 수가 renderer f32 필드에서 Inf로 넘쳐 `get_settings()`의 숫자가
  `null`이 되던 문제: GPU 사용 전 모델 숫자 변환과 직렬화 왕복을 검증.
- hi/lo로 표현 불가능한 유한 원본 수, 전체가 NaN/Inf인 배열을 명확한 메시지로 거부.
  f32 입력·hi/lo 인코딩 방식은 그대로 사용.
- 비문자 target/code 변수에서 내부 `AttributeError`가 노출되던 문제.
- notebook에서 native 선택·drag 메서드를 호출하던 문제: 지원 backend/브라우저
  작업 위치를 안내하는 `RuntimeError`로 처리.
- 잘못된 `show(block=...)`, widget backend/auto_prepare, 비유한 async timeout을
  전달 전에 거부. widget 연결/응답 timeout에 상황을 설명하는 메시지 추가.
- 브라우저에서 잘못된 설정을 정상 설정으로 복구해도 이전 오류 문구가 남던 문제:
  정상 설정 설치 시 오류를 해제하고 매 복구 후 이를 검증.

새 회귀 테스트는 `tests/test_invalid_state.py`에 있습니다. GPU 컬럼 할당 실패도
실제로 발생시켜 기존 차트와 pool이 보존되고 이후 render가 되는지 확인합니다.

## 실제 호스트·설치 검증

실제 X11 이벤트로 임의 선택·드래그·툴바 클릭·SSOT 편집·resize·닫기/재열기를
검사합니다. 정상 redraw/drag 중 컬럼 업로드·RGBA readback·PNG 인코딩 카운터가
증가하지 않는지도 확인합니다. notebook은 실제 JSON 편집 UI와 kernel revision
ack를 사용하며, 브라우저 설정/커널 `get_settings()` 일치와 복구를 검사합니다.

데스크톱은 seed 0–3의 **320개 동작**을 완료했습니다. 89개의 잘못된 설정을
오류로 처리했고, 44회 resize·44회 닫기/재열기·76회 포인터 동작을 처리했습니다.
6,850회 surface 제출 동안 일반 상호작용에서 컬럼 재업로드·RGBA readback·PNG
인코딩은 0회였습니다. DPI는 Xvfb 1.0입니다.

설치한 wheel의 실제 notebook에서 seed 9610의 **300회 편집** 중 279회를 오류로
거부하고 21회를 정상 처리했습니다. 모든 복구 뒤 설정과 오류 문구 상태를 확인했고,
브라우저 설정과 kernel 설정이 일치했습니다. initial upload는 2개 컬럼/2,048바이트를
유지했고 PNG 생성은 0회였습니다. 이후 명시적인 브라우저/커널 PNG 저장도 통과했습니다.

최종 wheel을 별도 venv에 설치하고 **42개 테스트 전체를 통과**했습니다
(127.99초, skip 0). 여기에는 실제 native surface·PNG fallback editor·JupyterLab
WASM/WebGPU의 자동/명시적 prepare 경로가 포함됩니다. native 확장과 8,112,575바이트
WASM·JS가 site-packages에서 로드되는 것을 확인했습니다.

호스트별 최종 집계와 설치 wheel 결과는 [호스트 결과 JSON](../reports/randomized-hosts.json)에
기록합니다. 일반 notebook 회귀 테스트는 기존 100,000개 입력을 유지하고, 300회
SSOT mutation 테스트는 256개 입력(2개 컬럼, 2,048바이트)을 사용합니다.

## 재실행

```sh
# 설치한 wheel 또는 maturin develop 환경에서
python scripts/check_randomized.py --seeds 32 --steps 500 --timeout 90 \
  --artifacts randomized-results/model

# DISPLAY, xdotool, xclip이 있는 Linux X11 환경에서
python scripts/check_randomized.py --backend native --phase ui \
  --seeds 4 --steps 80 --timeout 120 --artifacts randomized-results/desktop

# JupyterLab, playwright, Chromium, WebGPU 사용 가능 환경에서
FIGGY_TEST_JUPYTER=1 FIGGY_TEST_HEADFUL=1 FIGGY_FUZZ_BROWSER=1 \
  python -m pytest -q tests/test_jupyter_webgpu.py -k True

python -m pytest -q tests/test_invalid_state.py
```

단일 실패 seed 재현은 `--seed N --seeds 1 --backend native --phase concurrent`처럼
backend/phase를 지정합니다. 입력 seed는 재현 가능하지만 스레드 스케줄은 달라질 수
있습니다. 이 검증은 모든 입력/드라이버에 대한 교착 부재를 증명하지 않습니다.
실제 VRAM 고갈·대규모 OS 메모리 고갈, 모든 브라우저, Windows/macOS 하드웨어는
이번 무작위 캠페인의 검증 범위에 포함하지 않았습니다. CI 자동 실행은 비활성 상태를
유지합니다.
