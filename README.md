# figgy-python

[`figgy-renderer`](https://crates.io/crates/figgy-renderer)의 Python 바인딩과 pip 배포를 위한 저장소입니다.
현재는 클라우드 개발 환경의 기본 설정만 포함하며, 바인딩 코드와 Python 패키지 설정은 아직 없습니다.

## 클라우드 개발 환경

기존 체크아웃 `/workspace/figgy-python`을 사용합니다. 클라우드 작업은 이미 격리되어 있으므로 별도 Git worktree는 필요하지 않습니다.
Debian 13, Python 3.12, uv, C 컴파일러, curl, Debian 서명 키가 있는 Codex 클라우드 환경을 기준으로 합니다.

```bash
cd /workspace/figgy-python
bash scripts/setup-cloud.sh
source /workspace/.figgy-tools/activate.sh
```

설치 스크립트는 저장소 밖의 `/workspace/.figgy-tools`에 다음 항목을 준비합니다.

- Rust 1.99.0 (`figgy-renderer 0.16.1`의 최소 Rust 버전)
- Python 3.12 가상환경, pip, maturin, pytest, build, twine
- 창 없는 렌더링 검증에 사용할 Mesa 소프트웨어 Vulkan 드라이버
- Cargo 빌드 캐시와 최대 4개의 빌드 작업

새 셸에서도 `source /workspace/.figgy-tools/activate.sh`를 실행합니다. 별도 서버 프로세스는 필요하지 않습니다.
설치 시 GitHub, Rust 배포 서버, PyPI, crates.io, Debian 패키지 서버에 대한 네트워크 접근이 필요합니다.
TLS, 패키지 서명, Cargo 체크섬 검증을 유지합니다. PyPI 업로드 자격 증명은 개발 환경 설치에 필요하지 않습니다.

## 확인된 범위

환경 설정 당시 저장소 밖의 임시 샘플에서 `figgy-renderer 0.16.1`과 PyO3를 사용해 다음을 검증했습니다.

- Linux / CPython 3.12 wheel 빌드, pip 설치, 엄격한 twine 메타데이터 검사
- Python에서 네이티브 렌더러 함수 호출
- 소프트웨어 Vulkan으로 960×600 사인 곡선 PNG 생성
- Python 호출 및 PNG 검사 테스트 2개 통과
- 설치 스크립트 재실행 성공

임시 샘플, 설치된 도구, 생성된 wheel과 PNG는 이 저장소에 포함하지 않습니다.
이 결과는 개발 환경 검증이며, 실제 `figgy-python` 패키지나 manylinux·Windows·macOS 배포 검증 결과가 아닙니다.

## 다음 작업

PyO3 바인딩과 `pyproject.toml`/`Cargo.toml`을 구현하고 실제 패키지 테스트를 추가합니다.
프로젝트 설정이 생긴 뒤에는 활성화된 가상환경에서 `maturin develop --locked`와 프로젝트 테스트를 실행합니다.
배포 전에는 실제 wheel의 설치·렌더링 테스트와 플랫폼별 호환성을 검증해야 합니다.
