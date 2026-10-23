# Dynamic Drone Mission SITL v1.0.0

## Release Summary

Crazyflie 기체·센서·펌웨어, Virtual AI Deck/GVSoC GAP8, 5개 Arena 및 Host 영상·상태 인터페이스를 제공하는 **Mission SITL Simulation Platform** Production Baseline입니다. Host 인지·유도·FSM 및 자율비행 완성을 의미하지 않습니다.

## 기능과 환경

MuJoCo 3.16.0, Crazyflie SITL, IMU/Flow/ToF, EKF2/PID1, Native UART/CPI/SPI/CPX, Virtual ESP32 TCP5000을 유지합니다. 대상은 Ubuntu22.04.5 x86_64 및 ROS2 Humble 설치 환경입니다. Native 실행은 ROS Workspace를 요구하지 않습니다. 별도 Fresh Ubuntu VM/다른 PC Qualification은 미완료입니다.

## 설치

[초보자 README](README.md) 순서대로 `install.sh --check`, 고지 확인 후 `install.sh --accept-unverified-license`, `build.sh`, `verify.sh --smoke`를 실행합니다. Git Clone과 ZIP 모두 외부7개 저장소를 고정 Commit으로 직접 받으며 인터넷이 필요합니다.

## Arena / Rover / Host

Basic 기본값과 integrated/mission1/mission2/mission3/mission3_straight를 제공합니다. LOOP/GRID0·1/SHUTTLE reverse·turn, Straight0~0.30m/s 설정을 유지합니다. Host 입력은 324×244 Mono8와 Frame-associated Body FLU 상태입니다. 명령은 별도 CRTP UDP20050입니다.

## Validation Summary

기존 RC의25회/14,685프레임, Payload Match100%, CRC/Decode/Frame Gap0을 보존합니다. 당시 FPS19.32~20.19, Strict All-run20fps FAIL이었습니다. v1.0.0은 새 ZIP 경로의 공식 Upstream Bootstrap/Clean Build와 Basic+5Arena Native E2E로 재검증하며, 최종 측정값과 Commit/ZIP Hash는 실제 GitHub Release 본문 및 배포 보고서에 기록합니다. 무결성과 성능은 별도 게이트입니다. ARM/Takeoff/Land 시험을 실행하지 않습니다.

## Known Limitations

Host Perception/Guidance/Mission FSM/Autonomous Flight는 미구현, Powered Moving-Rover Landing은 미검증입니다. Rover는 prescribed mocap + surfacevel approximation이며 완전한 양방향 동역학이 아닙니다. Flow 모델은 moving surface 속도를 제거하지 않습니다. Clock Alignment/정밀 상태 보간은 없고 모든 PC에서20fps를 보장하지 않습니다.

## External Dependency Notices

[External Dependencies](docs/EXTERNAL_DEPENDENCIES.md)의 MIT 선언 근거와 LICENSE 원문 누락을 구분해 확인하십시오. drone-models 소스/Assets는 본 Git/ZIP에 포함하지 않습니다. 직접 Clone 또는 설치 고지 확인 옵션은 사용권을 부여하지 않습니다. 원문 및 Asset 범위 확인은 후속 Compliance 항목입니다. 자체 배포물과 허용된 Patch의 공개 가능성을 별도로 검사했습니다.

## ZIP / SHA256 / Handoff

[GitHub Releases](https://github.com/unLIMited72/Dynamic-Drone-Mission-SITL/releases)에서 v1.0.0의 `Dynamic-Drone-Mission-SITL-v1.0.0.zip` 및 `SHA256SUMS`를 받으십시오. Git Tag와 ZIP comment는 소스 Commit을 식별합니다. ZIP의 SHA256은 함께 제공하는 SHA256SUMS와 Release 본문을 기준으로 확인합니다. 오프라인 번들이 아닙니다.

이후 개발은 [Host PC Development Handoff](docs/HOST_PC_DEVELOPMENT_HANDOFF.md)의 독립 Host Application 계층에서 시작합니다.
