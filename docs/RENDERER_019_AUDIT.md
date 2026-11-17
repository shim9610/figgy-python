# Renderer 0.19 통합 점검 — 2026-11-17

Python PR [#23](https://github.com/shim9610/figgy-python/pull/23)에서 누락됐던
차트 편집 API, 프리셋 적용, 값 라벨 포맷과 SVG/PDF 인쇄 크기를 수정했다.
배포는 Figgy 0.19 정식 발행 후 정확한 공개 패키지 버전과 WASM을 고정하는
기존 순서를 따른다. 이 통합 커밋을 PyPI에 배포하지 않았다.

native renderer/model과 WebAssembly는 모두
[`c9828223409b8a9253e011572955aa7a729c7efe`](https://github.com/shim9610/figgy/commit/c9828223409b8a9253e011572955aa7a729c7efe)를 사용한다.
이 커밋에는 상위 이슈 #308, #309, #318의 수정이 들어 있다. 에너지 라벨 선택도
임시 메타데이터 우회 처리를 제거하고 공개 `selection_details()`를 사용한다.
상위 manifest의 개발 중 패키지 버전은 아직 renderer 0.18.1 / model 0.12.1이다.

## 수정 범위

- **이름 기반 편집:** 공통 시리즈로 바뀐 막대·박스·레이더에 `series`, `cell`,
  `set_value_labels`, `decoration`, `set_plot_bounds`, 방향 전환과 초기화 API를
  연결했다. 범주·시리즈 ID로 편집하며 기존 데이터 컬럼을 재업로드하지 않는다.
  개별 레이더 spoke 라벨은 새 `Category.label_offset`에 연결했다.
- **값 라벨:** 렌더러의 공개 `format_labels`, `format_box_plot_labels`,
  `format_radar_labels`로 실제 값·중앙값·표본 수를 포맷한다. native는 필요한 값을
  GPU에서 일시적으로 읽으며 원본 배열을 보관하지 않는다. notebook은 전송 버퍼가
  있을 때 그 버퍼를 쓰고, 전송 완료 후에는 브라우저 GPU 데이터로 처리한다.
  형식 변경은 재계산하지만 색·스타일 편집은 사용자가 지정한 라벨 문자열을 유지한다.
- **프리셋:** 기존 `bounded` 토큰을 공통 시리즈와 소유 패널에 연결했다.
  원본 데이터·범주·축 범위는 유지하며 명시적 생성 인자가 프리셋보다 우선한다.
  스타일 추출·재적용에도 차트 종류별 스타일과 인치당 해상도에 따른 길이 변환이 적용된다.
  벡터용 역할·기본 스타일이 다른 차트 종류의 구조에 들어가던 문제도 막았다.
- **인쇄 크기:** 렌더러의 96 논리 픽셀/인치 출력을 Figure DPI에 맞춘다.
  SVG는 루트의 물리 크기를, PDF는 페이지와 내용을 함께 변환한다.
  배율은 출력 해상도를 바꾸며 페이지의 인치 크기는 유지한다. native 저장 창과
  notebook의 비동기 출력 모두 같은 규칙을 따른다.
- **호환성 검사:** 없어진 최상위 `categorical`, `boxplot`, `radar` 필드를 검사하던
  테스트를 공통 Config·SeriesConfig, 리소스 연결, 데이터 보존과 실제 출력 검사로
  이관했다. 새 모델이 지원하는 축 범위·범례 위치와 큰 글꼴도 검사한다.

## 실행 결과

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| 최종 전체 회귀 | **1,740 통과 / 실패 0 / 179 건너뜀** | 기본 전체 실행; UI·외부 action 메타데이터 전용 검사는 별도 실행 |
| 0.19 호스트 묶음 | 20 통과 | 공통 상태 10개 + 실제 Jupyter 7개·native 창 3개 |
| 마지막 브라우저 변경 재검증 | 2 통과 | 상위 에너지 라벨 API 직접 사용, 버퍼 해제 후 사용자 지정 라벨 보존 |
| 기존 native 창 동작 | 2 통과 | 드래그·크기 변경·다시 열기·Python/UI PNG 일치 |
| 배포·자산·호스트 연동 사전 검사 | 109 통과 | workflow에 고정한 실제 maturin-action 메타데이터 포함 |

검사 범위는 서로 겹치므로 통과 수를 합산하지 않는다. 전체 회귀의 이전 결과는
1,437 통과 / 231 실패 / 177 건너뜀이었으며, 당시 자료는 Git 커밋 `449522a`에
남아 있다. 이번 결과와 소스·실행 로그 해시는
[기계 판독용 검증 자료](measurements/renderer-019-integration-audit-20261117.json)에 기록한다.

Linux X11/Xvfb·Mesa Vulkan과 실제 JupyterLab·Chromium WebGPU에서 검사했다.
실제 호스트 검사는 선택 정보, 테마 네 종류, 자동배치, 편집 후 출력과 페이지
크기를 확인한다. Windows/macOS 창과 물리 GPU 성능은 이번 검사 범위에 없다.

`figsize=(4, 3)`은 DPI 72·96·120·144와 배율 1·2에서 SVG/PDF 모두
**288 × 216 pt = 4 × 3 in**이다. subplot과 radial 페이지도 별도로 검사한다.

공통 차트의 재적용 코드는 `apply_settings(..., preserve_data=True)`로 원자적으로
설정을 적용한다. 대상의 과학 데이터와 바인딩을 유지하고 범주·토폴로지 불일치를
거부한다. 고급 모델의 코드가 항상 짧은 편의 API 호출로만 표현되는 것은 아니다.
재질의 미세한 grain은 GPU에 등록된 시리즈 ID를 seed로 사용하므로 독립 Figure의
픽셀 비교에서는 Flat 재질 또는 채널당 3/255 이하 오차를 사용하는 검사가 있다.

## NIST 입력

`read_nist(levels, lines=None)`는 CSV 경로·본문·텍스트 스트림·테이블을 읽고
configuration/term/J로 전이 끝점을 연결한다. 단위·수치 한정 기호·불확도·참고문헌을
보존한다. 표에 없는 준위의 전이는 기본적으로 오류이며 `unmatched='skip'`을
명시한 경우에만 제외 개수를 기록한다. URL 다운로드·단위 변환·전이 추론은 별도다.

| 실제 입력 | 준위 | 전이 | 이온화 한계 | 연결 누락 |
| --- | --- | --- | --- | --- |
| He I | 59 | 111 | 1 | 0 |
| Cu I | 35 | 69 | 1 | 0 |
| Ar I | 43 | 51 | 1 | 0 |

입력 원본은 [NIST 회귀 데이터](../tests/data/nist/README.md), 사용법은
[Python API 안내](RENDERER_019.md), 최종 배포 절차는 [PUBLISHING.md](PUBLISHING.md)를 따른다.
