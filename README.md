# Dynamic Drone Mission SITL

Crazyflie SITL + MuJoCo + Native GVSoC GAP8 + 5개 Mission 경기장 플랫폼입니다.
기본 경기장은 Basic이며, 기존 `run.sh`로 GUI/Headless를 관리합니다.

**배포 준비 RC — 외부 의존성 사용권 검토가 완료된 정식 Release가 아닙니다.**
필수 `utiasDSL/drone-models`의 고정 Commit에는 LICENSE가 없습니다. 그 소스는
이 저장소나 ZIP에 포함하지 않습니다. 직접 Clone도 사용·수정 권한을 부여하지
않습니다. 사용자는 원저작자에게 필요한 허가를 확인해야 합니다.
[외부 의존성과 미확인 사항](docs/EXTERNAL_DEPENDENCIES.md)을 먼저 읽어 주세요.

## 설치 흐름

Ubuntu **22.04.5 LTS x86_64**, Python3.10, ROS2 Humble 설치 환경이 대상입니다.
Native Runtime은 ROS2 Workspace를 빌드하지 않습니다. 최초 설치는 인터넷이
필요한 **Source + Bootstrap Distribution**입니다. 외부 소스·SDK·Toolchain은
[Lock](deps/external_repositories.lock.json)의 공식 URL과 Commit에서 받습니다.

```bash
git clone https://github.com/unLIMited72/Dynamic-Drone-Mission-SITL.git
cd Dynamic-Drone-Mission-SITL
./scripts/install.sh --check
# 미확인 외부 라이선스 고지를 읽고 기술 설치를 선택한 경우에만:
./scripts/install.sh --accept-unverified-license
./scripts/build.sh
./scripts/verify.sh --smoke
./virtual_aideck/run.sh start --gui
```

`--accept-unverified-license`는 위험 고지 확인 옵션이며 법적 허가가 아닙니다.
기본 install은 이 선택 없이 중단합니다. 누락된 apt 패키지는 목록을 표시하고
동의를 받은 뒤 sudo로 설치합니다. GPU 드라이버는 교체하지 않습니다.
ZIP도 압축 해제한 루트에서 같은 설치 명령을 사용하며 `.git`은 필요 없습니다.

## 구조와 기능

```text
MuJoCo → IMU/Flow/ToF → Crazyflie SITL Kalman2/PID1
  ├─ CRTP UDP20050 (외부 비행 제어)
  └─ Ego-State ~100Hz → UART bit model → GAP8 UART0/uDMA
Camera324×244 → Himax/CPI DMA → Frame + Latest State
  → Native CPX/SPI → Virtual ESP32 → TCP5000 Host
```

지원: Basic, integrated, mission1, mission2, mission3, mission3_straight.
Mission3 Rover: LOOP, GRID0/1, SHUTTLE reverse/turn. Straight: 0–0.30m/s,
기본0.15m/s. 기존 기체·EKF/PID·Flow·UART/CPX 계약을 유지합니다.

```bash
./virtual_aideck/run.sh start --headless
./virtual_aideck/run.sh status
./virtual_aideck/run.sh logs
./virtual_aideck/run.sh stop
# 현재 Runtime을 종료한 뒤 경기장 선택:
./virtual_aideck/run.sh start --gui --config virtual_aideck/config/arena_mission3.json
./virtual_aideck/run.sh stop --config virtual_aideck/config/arena_mission3.json
```

설정은 시작 시 적용됩니다. [설정 설명](docs/CONFIGURATION.md)에 경기장·속도·포트
예제가 있습니다. Viewer나 비행 명령은 자동으로 실행하지 않습니다.

## Host 영상·상태

```bash
Drone/bin/python virtual_aideck/runtime/host_protocol/e2e_client.py --frames 100 --out /tmp/image_state.json
```

한 TCP client만 연결하세요. 재사용 API는 `e2e_client.Client.receive()`이며
`(metadata, mono8)`를 반환합니다. 상태는 해당 프레임에 연결된 Body FLU 속도,
각속도, XYZW quaternion, EKF 높이, 별도 ToF/validity, specific force입니다.
[정확한 프로토콜](virtual_aideck/docs/E2E_IMAGE_STATE_PROTOCOL.md)을 참고하세요.

실시간 표시에는 기존 `host_protocol/preview.py`의 `Preview` API를 동일한
수신 루프에 붙일 수 있습니다. 별도 연구실 Live Viewer는 이 배포의 소스가
아니므로 포함하지 않습니다. 브라우저/Viewer 때문에 두 번째 TCP client를
연결하지 마세요. CRTP 제어 client와 TCP 영상 client는 병행 가능합니다.

## 검증과 지원 범위

```bash
./scripts/verify.sh --check
./scripts/verify.sh --build
./scripts/verify.sh --smoke
./scripts/verify.sh --e2e --scenario all --seconds 60
./scripts/verify.sh --e2e --scenario basic --seconds 15 --gui
```

Smoke는 실제 모델·렌더·접촉 검사이며 Native E2E와 구분합니다. E2E는 실제
SITL→UART→GAP8→SPI→TCP에서 영상 해시와 원본 상태 payload를 비교합니다.
포트가 점유되면 실패하며 기존 프로세스를 종료하지 않습니다. 비행 명령 없음.

- 실제 별도 Fresh Ubuntu VM/다른 PC Qualification은 미완료입니다.
- 같은 개발 서버의 독립 디렉터리·새 venv/SDK 검증은 Fresh OS 검증이 아닙니다.
- 최소 CPU/RAM/GPU 사양은 아직 확정하지 않았습니다. GUI는 DISPLAY/OpenGL,
  Headless는 EGL이 필요합니다. NVIDIA/Intel/AMD/Wayland 전체를 보장하지 않습니다.
- 약20fps는 측정 목표입니다. 과거 20fps 미만 실행도 있었으며 모든 PC에서
  또는 모든 실행에서 20fps를 보장하지 않습니다.
- Rover는 prescribed mocap + MuJoCo surfacevel **Moving Surface Approximation**입니다.
  접촉·마찰에 의한 passive transport이며 양방향 Rover 동역학이 아닙니다.
- 실제 powered moving-rover landing, Host Perception/Guidance/Mission FSM,
  autonomous mission flight는 포함하지 않습니다.
- STM32/GAP8 Clock Alignment·상태 보간이 없습니다. receive age는 원본 센서
  측정 나이나 UART 지연이 아닙니다.

[설치/업데이트](docs/INSTALLATION.md) · [문제 해결](docs/TROUBLESHOOTING.md) ·
[구조](docs/ARCHITECTURE.md) · [라이선스/고지](THIRD_PARTY_NOTICES.md).
자체 코드·Arena는 GPL-3.0, 허용된 외부 수정 Patch는 원래 고지를 유지합니다.
외부 프로젝트는 각각 별도 조건을 적용하며 사용권 전체가 확인됐다고 주장하지 않습니다.
