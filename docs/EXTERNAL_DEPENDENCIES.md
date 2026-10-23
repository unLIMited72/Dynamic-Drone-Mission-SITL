# External dependencies

이 배포는 **Internet-required Source + Bootstrap Distribution**입니다. 외부 프로젝트 전체 소스, SDK, 컴파일러와 venv는 Git Tree와 ZIP에 포함하지 않습니다. 설치 시 아래 원본에서 정확한 Commit을 확보합니다. 모두 Runtime/Build 의존성이며 확인 방법은 Remote, HEAD 및 허용된 Patch 비교입니다. 구체적인 명세는 `deps/external_repositories.lock.json`입니다.

| Name | Official repository / commit | 설치 경로 | License | 수정 |
|---|---|---|---|---|
| firmware | https://github.com/llanesc/crazyflie-firmware.git `aa6571dc465f06f7d1f9aaf7b0b861fbcd1b3d67` | `crazyflie-firmware` | GPL-3.0 | 없음 |
| freertos | https://github.com/FreeRTOS/FreeRTOS-Kernel.git `3604527e3b31991c596cd420f32989ee890aca4a` | `crazyflie-firmware/vendor/FreeRTOS` | MIT | 없음 |
| simulator | https://github.com/llanesc/crazyflie-simulation.git `89d8cf79fb722bf4bd7e363ade7d90d6c45d6d5d` | `crazyflie-firmware/tools/crazyflie-simulation` | MIT | deps/patches/simulator.patch |
| drone-models | https://github.com/utiasDSL/drone-models.git `512c864ffa55081ef4e80fadde2e861f22f45943` | `crazyflie-firmware/tools/crazyflie-simulation/simulator_files/mujoco/drone-models` | UNVERIFIED | 없음 |
| cflib | https://github.com/bitcraze/crazyflie-lib-python.git `3c1cb0d024fef6f45d08f0ad236a22ac395dd924` | `crazyflie-lib-python` | GPL-3.0 metadata; bundled LICENSE differs, retain upstream notices | 없음 |
| gap-sdk | https://github.com/GreenWaves-Technologies/gap_sdk.git `092a315287a149cf2280f8f47470c44e511f2090` | `third_party/gap_sdk` | Apache-2.0 plus per-file notices | deps/patches/gap-sdk.patch |
| toolchain | https://github.com/GreenWaves-Technologies/gap_riscv_toolchain_ubuntu_18.git `e6b5fbbfbf57a0ad1092efb280d0417cf3ee7e51` | `third_party/gap_riscv_toolchain` | GNU toolchain upstream binaries; no redistribution by this project | 없음 |

`drone-models`는 LICENSE가 확인되지 않았고 별도 허가도 없습니다. 원본에서 Clone하는 행위가 사용·수정·재배포 권한을 부여하지 않습니다. 프로젝트 관리자에게 라이선스/사용 허가를 확인해야 합니다. 설치의 `--accept-unverified-license`는 위험 고지 확인이며 법적 허가가 아닙니다. 이 의존성의 소스나 수정 Patch는 본 배포에 포함하지 않습니다. 전체 권한 검토 완료 및 정식 Release 승인을 선언하지 않습니다.

cflib의 프로젝트 메타데이터와 LICENSE 내용이 일치하지 않는 문제도 미해결 고지 사항입니다. 원본 고지를 유지합니다. GNU toolchain 구성요소에는 각각의 조건이 적용됩니다.

Simulator MIT 및 SDK Apache 계열의 로컬 수정만 Patch로 제공합니다. 자체 작성 Arena/Runtime은 GPL-3.0으로 제공됩니다. 외부 소스를 자체 코드로 재분류하지 않습니다.

Bootstrap은 기존 저장소의 Remote/HEAD/수정 내용을 검사합니다. 예상하지 않은 변경이나 Untracked 파일은 보존하고 오류로 종료합니다. 다른 Commit으로 대체하거나 reset/clean을 실행하지 않습니다. 설치 중 실패한 자료는 보존됩니다. `.git` 없는 ZIP에서도 동일하게 동작합니다.
