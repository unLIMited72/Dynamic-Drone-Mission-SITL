# Host PC 개발 인계 — v1.0.0

이 문서는 이후 개발할 Host Application의 입력·출력 계약입니다. Perception/Guidance/FSM 구현이나 비행시험 결과가 아닙니다. Simulator, Firmware, GAP8, Arena, UART/SPI/CPX/TCP는 현재 Baseline으로 유지합니다.

## Host 입력: TCP5000

`virtual_aideck/runtime/host_protocol/e2e_client.py`의 기존 Decoder를 재사용합니다. `Client.receive()`는 `(metadata, image_bytes)`를 반환하며 영상은 324×244 Mono8, 79,056바이트입니다. 이미지와 함께 받은 `metadata['association']`의 상태를 사용합니다. 별도 cflib Logging으로 Frame-associated 상태를 대체하지 않습니다.

| 항목 | 계약 |
|---|---|
| Image/Frame | Mono8, frame sequence, camera session |
| Velocity | Body FLU m/s |
| Angular rate | Body FLU P/Q/R rad/s |
| Quaternion | Body FLU→Local World, XYZW 순서 |
| EKF height | Local World +Z m; ToF와 다른 값 |
| ToF | Body−Z Ray 거리 m, 독립적인 tof_valid |
| Specific force | Body FLU m/s², 중력 제거된 선형 가속도로 간주하지 않음 |
| STM32 time | snapshot commit tick ms, boot/reset/sequence 함께 확인 |
| GAP8 time | DMA capture-end 관찰 및 UART parser 수신/검증 tick µs |

GAP8 receive age는 같은 GAP8 clock의 `capture - receive`입니다. 센서 측정 나이, UART 전달 지연 또는 STM32 clock과의 직접 차이가 아닙니다. Clock Alignment/상태 보간은 없습니다. 이미지가 도착해도 state_available/state_association_valid/tof_valid는 별도로 확인합니다. Boot/reset/session 변화와 stale 상태를 Host FSM이 처리해야 합니다. [정확한 Wire Contract](../virtual_aideck/docs/E2E_IMAGE_STATE_PROTOCOL.md)를 우선합니다.

연결/호출 예시는 수신 API 형태만 보여줍니다. Runtime과 연결을 소유할 Host가 필요하며 단일 TCP Consumer 정책을 지킵니다.

```python
# 프로젝트 runtime/host_protocol을 Python import path에 둔 Host Application에서 사용
from e2e_client import Client
client = Client(timeout=20)
try:
    metadata, mono8_bytes = client.receive()
    association = metadata['association']
finally:
    client.close()
```

선택적 Preview API는 `from preview import Preview`, `preview = Preview(8088)`, `preview.offer(mono8_bytes)`입니다. 같은 수신 루프를 공유하고 별도 TCP Client를 추가하지 않습니다. 이는 포함된 API이며 별도 연구실 Live Viewer 설치를 뜻하지 않습니다.

## Host 출력: CRTP UDP20050

주소는 `udp://127.0.0.1:20050`, 라이브러리는 고정 cflib입니다. 연결을 소유한 `Crazyflie` 인스턴스에서 지원하는 호출 형태:

```python
# API 서명 설명이며 이 문서를 실행해 자동 비행시키는 코드는 아닙니다.
cf.commander.send_hover_setpoint(vx, vy, yawrate, zdistance)
```

- `vx`, `vy`: body-fixed 수평 속도 m/s. 기체 기준 forward/left 방향의 명령으로 사용하며 World 속도 API와 구분합니다.
- `yawrate`: **degrees/s**. 수신 Ego-State의 angular rate(rad/s)를 그대로 넣지 않습니다.
- `zdistance`: **Local World 기준 절대 Z setpoint(m)**. 고정 Firmware의 hoverDecoder는 `modeAbs`와 `position.z`에 넣습니다. Rover 위 ToF나 Pad-relative 높이로 자동 변환되지 않습니다.
- 고정 cflib `Commander.send_hover_setpoint`는 프로토콜 버전 ≤8에서 legacy type과 yaw 부호 변환을 선택합니다. Firmware hoverDecoder도 내부 yaw 부호 변환을 수행합니다. 직접 패킷을 조립하거나 중복 부호 반전을 추가하지 말고 기존 API를 사용합니다. 실제 양·음 yaw 응답 비행시험은 별도 승인된 Flight Regression에서 확인해야 합니다.

근거는 설치 후 `crazyflie-lib-python/cflib/crazyflie/commander.py` 및 `crazyflie-firmware/src/modules/src/crtp_commander_generic.c`입니다. 이번 Release Qualification에서는 이 명령을 전송하지 않았습니다. 연속 setpoint 송신 주기, watchdog/timeout, 연결 상실과 중단 정책은 Host 개발에서 설계·검증해야 합니다. 한 번 호출했다고 지속적 Hover가 보장된다고 가정하지 않습니다. `run.sh stop`은 Simulator 종료이며 Landing 명령이 아닙니다.

## 권장 Host Application 구성

```text
Host E2E Receiver → Perception → Target/Obstacle State
                                      ↓
                                  Guidance
                                      ↓
                                 Mission FSM
                                      ↓
                             CRTP Command Sender
                                      ↓
                              Crazyflie SITL
```

이 계층을 기존 CrazySim Runtime에 강제로 합치지 않습니다. Receiver는 Frame/State 결합을 유지하고, Perception 결과에도 frame/session/timestamp를 전달합니다. 추정 대상의 좌표계·단위·유효성을 명시하고, Guidance 출력과 FSM 상태 전이를 분리합니다.

## 개발할 미션

- Mission1: ArUco ID1/2/3 인지·접근·이동. Integrated와 같은 Spawn, 별도 Entrance Gate 없음.
- Mission2: Ring/Building/Maze 인지와 장애물 Guidance.
- Mission3: Rover ID0 인지, 추적, 상대운동 추정 및 착륙 Guidance.
- Mission3 Straight: 등속 플랫폼을 이용한 상대운동/착륙 알고리즘 초기 시험.

Rover는 prescribed mocap + surfacevel approximation입니다. Flow 모델은 기체 운동/ToF에 기반하고 표면 속도를 제거하지 않으므로 Moving Pad 상대 Flow를 완전히 재현하지 않습니다. Passive Transport Smoke를 Powered Landing 성공으로 해석하지 않습니다.

새 Host 개발은 별도 애플리케이션과 별도 검증 자료로 진행합니다. 기존 Decode/Association/Protocol을 재사용하며 기체 질량·EKF/PID·센서·카메라·UART/SPI/CPX를 임의 변경하지 않습니다.
