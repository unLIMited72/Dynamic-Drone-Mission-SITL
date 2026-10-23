# External dependencies

이 배포는 **Internet-required Source + Bootstrap Distribution**입니다. 외부 프로젝트 전체 소스, SDK, 컴파일러와 venv는 Git Tree와 ZIP에 포함하지 않습니다. 설치 시 아래 원본에서 정확한 Commit을 확보합니다. 모두 Runtime/Build 의존성이며 확인 방법은 Remote, HEAD 및 허용된 Patch 비교입니다. 구체적인 명세는 `deps/external_repositories.lock.json`입니다.

| Name | Official repository / commit | 설치 경로 | License | 수정 |
|---|---|---|---|---|
| firmware | https://github.com/llanesc/crazyflie-firmware.git `aa6571dc465f06f7d1f9aaf7b0b861fbcd1b3d67` | `crazyflie-firmware` | GPL-3.0 | 없음 |
| freertos | https://github.com/FreeRTOS/FreeRTOS-Kernel.git `3604527e3b31991c596cd420f32989ee890aca4a` | `crazyflie-firmware/vendor/FreeRTOS` | MIT | 없음 |
| simulator | https://github.com/llanesc/crazyflie-simulation.git `89d8cf79fb722bf4bd7e363ade7d90d6c45d6d5d` | `crazyflie-firmware/tools/crazyflie-simulation` | MIT | deps/patches/simulator.patch |
| drone-models | https://github.com/utiasDSL/drone-models.git `512c864ffa55081ef4e80fadde2e861f22f45943` | `crazyflie-firmware/tools/crazyflie-simulation/simulator_files/mujoco/drone-models` | MIT_DECLARED_LICENSE_FILE_MISSING | 없음 |
| cflib | https://github.com/bitcraze/crazyflie-lib-python.git `3c1cb0d024fef6f45d08f0ad236a22ac395dd924` | `crazyflie-lib-python` | GPL-3.0 metadata; bundled LICENSE differs, retain upstream notices | 없음 |
| gap-sdk | https://github.com/GreenWaves-Technologies/gap_sdk.git `092a315287a149cf2280f8f47470c44e511f2090` | `third_party/gap_sdk` | Apache-2.0 plus per-file notices | deps/patches/gap-sdk.patch |
| toolchain | https://github.com/GreenWaves-Technologies/gap_riscv_toolchain_ubuntu_18.git `e6b5fbbfbf57a0ad1092efb280d0417cf3ee7e51` | `third_party/gap_riscv_toolchain` | GNU toolchain upstream binaries; no redistribution by this project | 없음 |

## drone-models: 선언 근거와 남은 범위

상태: **MIT_DECLARED_LICENSE_FILE_MISSING**. 고정 Commit의 [pyproject.toml](https://github.com/utiasDSL/drone-models/blob/512c864ffa55081ef4e80fadde2e861f22f45943/pyproject.toml)은 MIT Classifier를 선언하고 LICENSE 파일을 참조합니다. 하지만 그 Commit의 Git Tree에는 LICENSE 원문이 없습니다.

[PyPI 0.1.0b0](https://pypi.org/project/drone-models/0.1.0b0/) 메타데이터에도 MIT Classifier가 있습니다. JSON의 `license` 필드 자체는 null이므로 이를 별도의 LICENSE 원문으로 해석하지 않습니다. 후속 [Crazyflow의 고정 MIT LICENSE](https://github.com/utiasDSL/crazyflow/blob/44752d1b87496f25b44da6584ea68e06fb7ee11b/LICENSE)도 확인했습니다. 후속 LICENSE가 과거 Commit 및 모든 STL/3D Asset에 자동 소급 적용된다고 단정하지 않습니다.

MIT 선언의 근거를 인정하면서 원문 및 개별 Asset 범위 확인을 후속 Compliance 항목으로 남깁니다. 확인한 자료에서 명시적 사용 금지조건은 발견하지 않았습니다. 이는 모든 사용·수정·재배포 권한에 대한 법적 보증이 아닙니다. 별도 원저작자 허가를 확보했다고 주장하지 않습니다.

이 Repository와 Release ZIP에는 drone-models 코드/Asset/수정 Patch를 포함하지 않습니다. 설치 시 공식 Upstream의 정확한 Commit에서 모델 리소스를 받으며 해당 Python 패키지 전체를 pip 설치하는 구조는 아닙니다. `--accept-unverified-license`는 이 고지의 확인이며 법적 허가가 아닙니다. 상태 이름을 바꾸어도 옵션 요구는 유지합니다.

## 다른 외부 의존성과 수정

cflib 메타데이터는 GPL-3.0, LICENSE.txt는 GPL-2.0 텍스트입니다. 실제 commander.py 등에는 GPL-2.0-or-later 고지가 있어 GPL3 표기와 함께 읽어야 합니다. 전체 파일을 임의로 재라이선스하지 않고 원본 고지를 유지합니다. GNU Toolchain 구성요소는 각각의 원본 조건을 따릅니다.

Simulator MIT 및 SDK Apache 계열의 로컬 수정만 Patch로 제공합니다. 자체 작성 Arena/Runtime은 GPL-3.0입니다. 외부 소스를 자체 코드로 재분류하지 않습니다. Upstream Lock의 URL/Commit/목적/설치 경로와 Patch Hash를 설치 시 확인합니다.

Bootstrap은 기존 저장소의 Remote/HEAD/Staged/수정/Untracked 파일을 보호하며 예상과 다르면 종료합니다. 임의 최신 Commit으로 대체하거나 reset/clean하지 않습니다. `.git` 없는 ZIP에도 같은 설치 절차를 사용합니다. 외부 소스 전체, SDK, 바이너리, venv는 Git/ZIP에 포함하지 않습니다. 최초 설치에는 인터넷이 필요합니다.
