# Dynamic Drone Mission SITL v1.0.0

실제 Crazyflie 기체 없이 드론 인지·유도·미션 소프트웨어를 개발하기 위한 **Mission SITL Simulation Platform**입니다. 기체 물리, 센서, 실제 비행 펌웨어, 가상 AI Deck, 미션 경기장과 Host PC 영상·상태 인터페이스를 제공합니다. 실제 하드웨어와 100% 동일한 환경은 아니며 자율 미션 알고리즘은 아직 포함하지 않습니다.

처음 사용하는 팀원은 아래 설치 순서부터 따라오세요. 명령은 별도 안내가 없으면 **Clone 또는 ZIP 해제 후 프로젝트 최상위 폴더**에서 실행합니다.

## 1. 무엇을 제공하나요?

- **Software In The Loop (SITL)**: 실제 Crazyflie 제어 펌웨어를 PC에서 실행하고 가상 기체에 연결합니다.
- **MuJoCo / CrazySim**: 드론의 위치·자세·모터·접촉을 계산하는 물리 시뮬레이션입니다.
- **Flow Deck**: IMU(가속도·각속도 센서), Optical Flow(표면 영상의 이동량), ToF(빛의 비행시간을 이용한 거리)를 모사합니다. Kalman EKF(Extended Kalman Filter)가 상태를 추정하고 PID Controller가 기체를 제어합니다.
- **Virtual AI Deck / GAP8**: 드론 탑재 AI 보드와 임베디드 프로세서를 GVSoC에서 실행합니다. 실제 Camera CPI/DMA, UART, SPI/CPX 경로를 사용합니다. 완성된 인지 모델은 포함하지 않습니다.
- Basic 기본 장면과 **5개 Mission Arena**, Rover 주행 및 마찰 접촉, GUI/Headless 실행을 제공합니다.
- Host PC는 약20Hz 목표의 **324×244 Mono8 영상과 해당 프레임에 연결된 Ego-State(기체 자신의 상태)**를 받습니다.

## 2. 데이터는 어떻게 이동하나요?

```text
MuJoCo / CrazySim ── Drone Dynamics
  │
  ├─ IMU / Optical Flow / ToF → Crazyflie SITL Firmware
  │                              ├─ Kalman EKF(2) / PID(1)
  │                              └─ STM32 Ego-State Snapshot
  │                                    ↓ Virtual UART
  │                                  GAP8 UART/uDMA ─────────┐
  └─ FPV Camera → Virtual Himax → GAP8 CPI/DMA ───────────────┤
                                                            ↓
                                                Image + Latest Ego-State
                                                            ↓
                                                    Native CPX-over-SPI
                                                            ↓
                                                      Virtual ESP32
                                                            ↓ TCP5000
                                                          Host PC

Host cflib → CRTP udp://127.0.0.1:20050 → Crazyflie SITL (비행 명령)
```

**TCP5000은 영상·상태 수신**, **CRTP UDP20050은 비행 명령 전달**에 사용합니다. TCP의 상태는 STM32→GAP8→ESP32 경로를 실제 통과합니다. cflib Radio Logging으로 상태를 대신 만든 결과가 아닙니다. 상세 구조는 [Architecture](docs/ARCHITECTURE.md)를 참고하세요.

## 3. 필요한 환경

- Ubuntu **22.04.5 LTS**, x86_64, Python 3.10
- ROS 2 Humble 설치, 인터넷 연결, Git, 필요 패키지 설치를 위한 sudo
- 외부 SDK·컴파일러·venv·빌드 결과를 저장할 공간: RC 검증 디렉터리 약2.39GB. 다운로드/임시 빌드/로그에는 추가 공간이 필요하며 최소 용량 보장은 아닙니다.
- GUI: Display와 OpenGL. Headless: EGL. Installer는 GPU Driver를 교체하지 않습니다.

검증 참고 서버는 Ryzen 9 9950X, RAM 약60GiB, RTX4090입니다. 이는 최소 사양이 아닙니다. CPU/RAM/GPU 최소 요구사항 및 다른 GPU/Wayland 전체 지원은 아직 확정하지 않았습니다. 별도 Fresh Ubuntu VM/팀원 PC 시험과 같은 서버의 격리 설치 시험을 구분합니다.

ROS2 Humble은 설치 전제지만 **Native Runtime은 ROS2 Workspace를 빌드하거나 실행하지 않습니다.**

## 4. 처음 설치하기

### STEP 1 — OS와 ROS 확인

어느 터미널에서든 실행할 수 있습니다.

```bash
cat /etc/os-release
uname -m
echo "$ROS_DISTRO"
test -f /opt/ros/humble/setup.bash && echo "Humble setup exists"
```

Ubuntu 22.04 및 `x86_64`를 확인합니다. `ROS_DISTRO`가 비어 있어도 ROS가 미설치라는 뜻은 아닙니다. 새 터미널에서 ROS 환경을 아직 읽지 않았을 수 있습니다. 필요하면 `source /opt/ros/humble/setup.bash` 후 다시 확인하세요. 다른 ROS_DISTRO가 설정돼 있으면 깨끗한 Humble 터미널을 사용합니다. Native Python 환경은 ROS의 PYTHONPATH를 상속하지 않도록 구성합니다.

### STEP 2 — 소스 받기

원하는 상위 디렉터리에서 실행합니다. git이 없으면 Ubuntu의 git 패키지를 먼저 설치하세요.

```bash
git clone https://github.com/unLIMited72/Dynamic-Drone-Mission-SITL.git
cd Dynamic-Drone-Mission-SITL
```

정식 배포 기준은 `v1.0.0` Tag입니다. 새 Clone에서 `git checkout --detach v1.0.0`으로 고정할 수 있습니다. 기존 수정 사항이 있는 작업 폴더를 강제로 되돌리지 마세요.

ZIP 사용자는 [GitHub Releases](https://github.com/unLIMited72/Dynamic-Drone-Mission-SITL/releases)에서 v1.0.0의 `Dynamic-Drone-Mission-SITL-v1.0.0.zip`과 `SHA256SUMS`를 받습니다. 같은 폴더에서 `sha256sum -c SHA256SUMS`로 확인한 뒤 ZIP을 해제하고 그 안의 프로젝트 루트로 이동합니다. ZIP에는 `.git`이 없어도 됩니다. 외부 의존성을 받으려면 Git과 인터넷이 필요합니다.

### STEP 3 — 설치 전 검사

```bash
./scripts/install.sh --check
```

OS, 패키지, 외부 저장소, Python, SDK를 **변경 없이** 검사합니다. 첫 설치에서는 Missing dependency 등으로 종료될 수 있으며 정상적인 사전 진단입니다. 설치 후에는 누락 없음, 고정 HEAD, MuJoCo 3.16.0 및 SDK import 성공이 표시돼야 합니다.

### STEP 4 — 의존성 설치

먼저 [외부 의존성 고지](docs/EXTERNAL_DEPENDENCIES.md)를 읽습니다. drone-models에는 MIT 선언이 있지만 고정 Commit의 LICENSE 원문이 누락돼 있습니다.

```bash
./scripts/install.sh --accept-unverified-license
```

이 옵션은 **고지 확인이며 법적 허가를 부여하지 않습니다.** 설치 도구는 누락 apt 패키지를 표시하고 확인 후 sudo로 설치합니다. 공식 Upstream 7개를 정확한 Commit으로 Clone하고 새 Python venv와 GAP8 SDK를 구성합니다. 다운로드와 빌드에는 시간이 걸립니다. 완료되면 `INSTALL COMPLETE`가 출력됩니다.

실패 시 표시된 단계와 `.local/logs/`를 확인하세요. 기존 외부 저장소의 예상하지 않은 수정/Staged/Untracked 파일은 덮어쓰지 않고 중단합니다. 원인을 보존한 뒤 같은 명령으로 재시도할 수 있습니다. `--yes`는 apt 설치 확인을 생략하므로 설치 목록을 이해한 경우에만 사용하세요.

### STEP 5 — 펌웨어 빌드

```bash
./scripts/build.sh
```

Crazyflie SITL, Native 가상 주변장치와 GAP8 펌웨어를 생성합니다. 정상 종료는 `BUILD COMPLETE`입니다. 이 명령은 기체를 실행하거나 이륙시키지 않습니다. 실패하면 `.local/logs/firmware-build.log`, `gap8-build.log`와 콘솔의 최초 오류를 확인합니다. 불완전한 빌드 폴더를 무조건 삭제하지 마세요.

### STEP 6 — 모델·렌더·접촉 확인

```bash
./scripts/verify.sh --smoke
```

Basic과 5개 경기장을 실제 MuJoCo로 로드하고 영상을 렌더링합니다. Rover 접촉 Smoke도 포함합니다. JSON 결과의 PASS와 정상 종료를 확인합니다. 결과는 `.local/verification/`에 남습니다. 이는 펌웨어 전체 경로의 E2E 시험과는 다릅니다.

### STEP 7 — 첫 GUI 실행

```bash
./virtual_aideck/run.sh start --gui
```

MuJoCo 창과 드론/Basic 장면이 나타나고 터미널에 `status: running` 등의 Runtime 상태가 출력돼야 합니다. Camera/Sensor/Firmware/GAP8/ESP32가 시작돼 Host 연결을 기다립니다. GUI 창은 물리 장면을 보여주며 TCP FPV Viewer와는 다릅니다. **자동 이륙이나 미션 명령은 전송하지 않습니다.**

## 5. 실행·확인·종료

| 명령 | 용도와 확인할 것 |
|---|---|
| `./virtual_aideck/run.sh start --gui` | GUI 포함 시작. 실행 중이면 중복 시작하지 않음 |
| `./virtual_aideck/run.sh start --headless` | GUI 없이 EGL 렌더링과 전체 Native 경로 실행 |
| `./virtual_aideck/run.sh status` | Supervisor/자식 프로세스 상태 확인 |
| `./virtual_aideck/run.sh logs` | 현재 실행 로그 위치와 내용 확인 |
| `./virtual_aideck/run.sh stop` | 자신이 시작한 Runtime 전체 정상 종료 |

GUI 창만 닫는 것을 Supervisor 전체 종료와 혼동하지 마세요. 먼저 `stop`을 사용합니다. stop은 착륙 명령이 아닙니다. 사용자 정의 프로파일을 썼다면 status/logs/stop에도 같은 `--config`를 사용하세요. 다른 사용자의 Runtime/Viewer/수신기를 종료하지 않습니다.

## 6. Basic과 5개 미션 경기장

| 설정 | 환경과 용도 |
|---|---|
| Basic (`runtime.json`) | 기본 기체·센서·통신 확인 장면 |
| integrated | Mission1→2→3 연속 경기장 |
| mission1 | ArUco ID1/2/3 인지·접근 연구. Integrated와 같은 초기 위치/방향 |
| mission2 | Ring, Building, Maze 장애물 인지·유도 연구 |
| mission3 | 움직이는 Rover의 ID0/착륙 플랫폼 추적 연구 |
| mission3_straight | 고정 Heading의 직선 등속 Rover, 상대운동 연구 |

경기장은 시험 환경이며 자동 비행 경로를 실행하는 Mission FSM이 아닙니다.

## 7. 설정 바꾸기

**방법 A: 완성된 프로파일 선택**

```bash
./virtual_aideck/run.sh stop
./virtual_aideck/run.sh start --gui \
  --config virtual_aideck/config/arena_integrated.json
./virtual_aideck/run.sh status --config virtual_aideck/config/arena_integrated.json
./virtual_aideck/run.sh stop --config virtual_aideck/config/arena_integrated.json
```

파일명을 `arena_mission1.json`, `arena_mission2.json`, `arena_mission3.json`, `arena_mission3_straight.json`으로 바꾸면 됩니다.

**방법 B: 기본 `virtual_aideck/config/runtime.json` 편집**

기존 최상위 JSON 객체에 `arena` 항목을 추가하거나 수정합니다. Basic으로 돌아가려면 arena 항목을 제거합니다. **Flow Deck, Port, state_link 등 나머지 설정은 보존하세요. 아래 예제로 전체 JSON 파일을 덮어쓰지 않습니다.** 설정은 시작 시 읽으므로 stop 후 다시 start해야 적용됩니다.

## 8. Mission3 Rover 주행 설정

Integrated와 Mission3는 같은 Controller를 사용합니다. 다음은 기존 JSON에서 수정할 **부분 객체**입니다.

```json
{"arena":{"scenario":"mission3","rover":{"mode":"grid","grid_route":0,"speed_mps":0.20}}}
```

| 주행 | rover 설정 |
|---|---|
| LOOP | `"mode":"loop"` |
| GRID0 | `"mode":"grid", "grid_route":0` |
| GRID1 | `"mode":"grid", "grid_route":1` |
| SHUTTLE Reverse | `"mode":"shuttle", "shuttle_behavior":"reverse"` |
| SHUTTLE Turn | `"mode":"shuttle", "shuttle_behavior":"turn"` |

모든 모드의 검증된 `speed_mps` Preset은 **0.10 / 0.15 / 0.20 / 0.30m/s**입니다. 목표/상한 속도이며 곡률·가속·조향·정지·반전 정책 때문에 순간속도가 항상 같지는 않습니다. 기존 `shuttle_reverse`, `shuttle_turn` 별칭도 유지됩니다. 상세 옵션은 [Configuration](docs/CONFIGURATION.md)에 있습니다.

## 9. Straight 속도

`arena_mission3_straight.json`의 arena/rover 부분을 수정합니다.

```json
{"arena":{"scenario":"mission3_straight","rover":{"speed_mps":0.15,"startup_delay_s":0.0,"duration_s":180.0}}}
```

속도는 **0~0.30m/s 유한 실수**, 기본 0.15m/s입니다. `startup_delay_s` 이후 고정 Heading으로 직선 등속 이동합니다. `duration_s`는 도로 시각적 길이 `speed × duration + 2.65m`를 설정하는 값이며 **해당 시간에 자동 정지한다는 뜻이 아닙니다.** U-turn/Loop/Teleport하지 않으며 충돌 바닥은 무한 평면입니다.

## 10. Camera와 Ego-State 받기

Runtime이 실행 중인 별도 터미널에서 프로젝트 루트로 이동한 뒤 실행합니다.

```bash
Drone/bin/python virtual_aideck/runtime/host_protocol/e2e_client.py \
  --frames 100 --out /tmp/image_state.json
```

기존 검증용 수신기가 TCP5000에서 100프레임을 수신하고 JSON 기록을 저장합니다. 창을 띄우는 Live Viewer 명령은 아닙니다. 수신이 끝나면 종료합니다. 같은 TCP 포트에 **수신기는 하나만** 연결하세요. E2E 시험 전에 이 수신기를 종료해야 합니다.

입력은 Mono8 영상(324×244), Frame ID, Body FLU velocity(m/s), angular rate P/Q/R(rad/s), quaternion XYZW, EKF height(m), ToF/validity, specific force(m/s²), STM32/GAP8 시간 정보입니다. FLU는 Forward/Left/Up 좌표입니다.

재사용 API는 `e2e_client.Client.receive()` → `(metadata, image_bytes)`입니다. 선택적 `preview.Preview(port).offer(image_bytes)`를 동일 수신 루프에 연결할 수 있습니다. 외부 연구실 Live Viewer는 배포에 포함하지 않습니다. [Host 개발 인계](docs/HOST_PC_DEVELOPMENT_HANDOFF.md)와 [Wire Protocol](virtual_aideck/docs/E2E_IMAGE_STATE_PROTOCOL.md)을 참고하세요.

## 11. Native E2E 검증

자신의 Runtime과 TCP 수신기를 정상 종료한 후 실행합니다.

```bash
./scripts/verify.sh --check
./scripts/verify.sh --build
./scripts/verify.sh --smoke
./scripts/verify.sh --e2e --scenario all --seconds 60
```

- `--check`: 설치 상태 검사. `--build`: 기존 Build 실행.
- `--smoke`: 실제 모델/렌더/짧은 무추력 접촉 검사. Native 통신 검증을 대신하지 않습니다.
- `--e2e`: 시험용 Runtime을 직접 시작하고 실제 SITL→UART→GAP8 CPI→SPI/CPX→ESP32→TCP를 검사한 뒤 종료합니다. 영상 Hash와 원본 UART 상태 Payload를 비교합니다. Basic과 5개 Arena를 순서대로 실행하므로 시간이 걸립니다.

포트가 점유돼 있으면 기존 프로세스를 강제로 종료하지 않고 실패합니다. 각 실행의 `.local/verification/native_*/summary.json`에서 integrity, fps, match_ratio, gaps를 확인하세요. GUI E2E는 `./scripts/verify.sh --e2e --scenario basic --seconds 15 --gui`입니다. 시험 중 ARM/Takeoff/Land는 실행하지 않습니다.

이전 RC의 **25회/14,685프레임, Payload 일치율100%, CRC/Decode/Frame Gap0** 결과를 보존합니다. 개별 FPS는 19.32~20.19였으며 Strict All-run20fps는 FAIL이었습니다. v1.0.0 결과는 Release Notes를 확인하세요. 작은 FPS 미달과 무결성 오류는 별도로 평가합니다.

## 12. 폴더 구조

| 위치 | Git/ZIP 포함 여부와 역할 |
|---|---|
| `scripts/` | 포함: 설치·빌드·검증·Upstream Bootstrap |
| `deps/` | 포함: 고정 Commit/패키지 목록, 허용된 Patch, Asset Hash, 고지 |
| `docs/` | 포함: 설치/설정/구조/문제 해결/Host 인계 |
| `virtual_aideck/` | 포함: run.sh, Config, 자체 Runtime/Arena/Assets/Protocol |
| `crazyflie-firmware/`, `crazyflie-lib-python/` | 설치 시 공식 Upstream에서 생성, Git/ZIP 제외 |
| `third_party/`, `Drone/` | SDK/Toolchain 및 Python venv, 설치 시 생성 |
| `.local/`, Runtime build/logs/state | 실행·빌드 산출물, Git/ZIP 제외 |

외부 코드 전체나 개발 Archive를 포함한 오프라인 번들이 아닙니다.

## 13. 문제 해결

| 증상 | 먼저 확인할 명령과 조치 |
|---|---|
| 패키지/venv 누락 | `./scripts/install.sh --check`; 실패 단계와 apt 목록 확인 후 설치 재시도 |
| pip 충돌/MuJoCo Import | `Drone/bin/python -m pip check`; `Drone/bin/python -c 'import mujoco; print(mujoco.__version__)'` |
| GAP8 SDK/RISC-V 누락 | `./scripts/bootstrap_external.sh --check`; `.local/logs/sdk-build.log` 확인 |
| GUI가 안 열림 | `echo "$DISPLAY"`; Display/Driver 확인. `start --headless`로 대체 시험 |
| Port occupied | `./virtual_aideck/run.sh status`; `ss -ltnp`, `ss -lunp`로 점유 확인. 타인 프로세스 종료 금지 |
| TCP5000 연결 실패 | Runtime `status`/`logs`에서 Firmware/GAP8/ESP32 상태와 다른 수신기 확인 |
| JSON 문법 오류 | `python3 -m json.tool virtual_aideck/config/arena_mission3.json`; 쉼표/따옴표 확인 |
| Arena Asset 누락 | `python3 scripts/check_source.py`; 원본 배포 파일과 Hash 확인. 임의 다른 Asset으로 대체하지 않음 |
| FPS가20미만 | 실행별 fps, CPU/GPU 부하와 software rendering 확인. 해상도/프로토콜을 바꿔 성공으로 처리하지 않음 |
| 정상 종료가 안 됨 | 같은 Config로 `status`, `logs`, `stop`; 로그를 보존하고 타인 프로세스를 종료하지 않음 |

세부 진단은 [Troubleshooting](docs/TROUBLESHOOTING.md), 운영은 [Runtime](virtual_aideck/docs/RUNTIME.md), 재설치/업데이트는 [Installation](docs/INSTALLATION.md)을 참고하세요.

## 14. 알려진 한계

- Host Perception, Guidance, Mission FSM, Autonomous Mission Flight는 미구현입니다.
- 실제 Powered Moving-Rover Landing은 검증하지 않았습니다.
- Rover는 Prescribed Mocap + MuJoCo surfacevel의 **Moving Surface Approximation**입니다. 접촉·마찰의 Passive Transport이며 완전한 양방향 Rover 동역학이 아닙니다.
- Optical Flow는 기체 운동과 ToF를 이용한 근사이며 접촉 표면/Rover의 접선 속도를 빼지 않습니다. 움직이는 Pad 위 상대 Flow를 완전히 재현하지 않습니다.
- 모든 PC/실행에서20fps를 보장하지 않습니다. GUI/Driver 차이와 부하에 영향을 받습니다.
- 같은 Ubuntu 서버의 격리 설치는 검증했으나 별도 Fresh Ubuntu VM/팀원 PC 검증은 미완료입니다.
- Clock Alignment와 정밀 State Interpolation/SLERP는 없습니다. GAP8 receive age는 센서의 실제 측정 나이나 UART 지연이 아닙니다.

## 15. 라이선스와 외부 의존성

자체 코드·Arena는 GPL-3.0, 외부 수정 Patch는 원래 고지를 유지합니다. 외부 소스 7개는 정확한 공식 URL/Commit에서 직접 받습니다. [External Dependencies](docs/EXTERNAL_DEPENDENCIES.md), [Third-party Notices](THIRD_PARTY_NOTICES.md), [LICENSE](LICENSE)를 확인하세요.

drone-models의 상태는 **MIT_DECLARED_LICENSE_FILE_MISSING**입니다. 고정 pyproject/PyPI의 MIT 선언 근거와 LICENSE 원문 누락을 함께 고지합니다. 후속 Crazyflow의 MIT LICENSE를 과거 Commit/모든3D Asset에 소급 적용한다고 단정하지 않습니다. 직접 Clone이나 설치 옵션이 사용·수정·재배포 권한을 새로 부여하지 않습니다. 원저작자의 명확한 원문/Asset 범위 확인은 후속 Compliance 항목입니다.

## 16. v1.0.0 Release와 다음 개발

버전/Tag: **v1.0.0**, 제목: **Dynamic Drone Mission SITL v1.0.0**.

실제 게시 내역은 [GitHub Releases](https://github.com/unLIMited72/Dynamic-Drone-Mission-SITL/releases), 설명은 [Release Notes](RELEASE_NOTES.md)에 있습니다. v1.0.0 Assets의 `Dynamic-Drone-Mission-SITL-v1.0.0.zip`과 `SHA256SUMS`를 사용하세요. ZIP Hash는 그 SHA256SUMS 및 Release 설명에 기록합니다. 설치 시 인터넷이 필요한 Source + Bootstrap Distribution입니다.

다음 단계는 독립 Host Application의 **Perception → Guidance → Mission FSM → CRTP 명령** 개발입니다. [Host PC Development Handoff](docs/HOST_PC_DEVELOPMENT_HANDOFF.md)에서 입력·출력 계약과 기존 Decoder 재사용 경로를 확인하세요. Simulator/Firmware/GAP8/E2E Baseline은 유지합니다.
