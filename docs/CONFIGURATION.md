# Runtime configuration

기본 `virtual_aideck/config/runtime.json`은 Basic입니다. 선택 가능한 Arena는 정확히 integrated, mission1, mission2, mission3, mission3_straight이며 각 `arena_<scenario>.json`을 사용합니다. 설정 변경 후 stop/start가 필요합니다. run.sh 인터페이스는 유지됩니다.

```bash
./virtual_aideck/run.sh start --headless --config virtual_aideck/config/arena_integrated.json
./virtual_aideck/run.sh stop
```

| 설정 | 의미 |
|---|---|
| source_sim_fps | 시뮬레이션 영상 생성률, Host FPS 보장값 아님 |
| flowdeck | Flow Deck 사용 |
| firmware_udp_port | SITL 연결, 기본 20150 |
| crtp_udp_port | CRTP 제어, 기본 20050 |
| camera_udp_port | Camera 전달, 기본 15200 |
| cpx_tcp_port | Host TCP, 기본 5000 |
| state_link | Native UART 상태 전송 및 Frame-State Association |
| arena.scenario | 5개 Arena 중 선택 |
| arena.rover.mode | loop/grid/shuttle |
| arena.rover.grid_route | 0 또는 1 |
| arena.rover.shuttle_behavior | reverse 또는 turn |
| arena.rover.speed_mps | 기존 Controller 목표 속도; 순간속도는 곡률/가속 정책에 따라 변함 |
| arena.rover.startup_delay_s | Straight 이동 시작 지연 |
| arena.rover.duration_s | Straight 도로 시각적 길이 설계 시간 |

Integrated/Mission3의 예:

```json
{"arena":{"scenario":"mission3","rover":{"mode":"grid","grid_route":1,"speed_mps":0.20}}}
```

LOOP은 `mode: loop`, SHUTTLE은 `mode: shuttle`과 `shuttle_behavior: reverse` 또는 `turn`을 사용합니다. 기존 검증된 속도는 0.10/0.15/0.20/0.30 m/s입니다. 다른 Runtime 항목을 지우지 말고 해당 Rover 항목만 편집하십시오.

Straight 예:

```json
{"arena":{"scenario":"mission3_straight","rover":{"speed_mps":0.15,"startup_delay_s":0.0,"duration_s":180.0}}}
```

Straight는 0.0–0.30 m/s 유한 실수를 사용하며 고정 Heading/등속입니다. 도로 길이는 `speed * duration + 2.65m`, 충돌 바닥은 무한 평면입니다. 기간 이후 역전/Teleport하지 않습니다. 잘못된 Mode/Key/Route/음수/NaN/Infinity/Scenario 조합은 시작 전 Validator 오류로 거부합니다.

Pad는 0.50×0.40m, 상면 0.30m, ID0이며 Moving Surface Approximation을 사용합니다. Contact/friction으로 수동 운반하지만 Rover 자체는 Prescribed Motion입니다. 양방향 Rover 동역학이나 Powered Landing 검증과 동일하지 않습니다.
