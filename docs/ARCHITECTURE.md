# Native architecture

MuJoCo → Crazyflie SITL(IMU/Flow/ToF, EKF2/PID1) → STM32 Body FLU Snapshot → Virtual UART → GAP8 UART/uDMA → CPI/DMA Camera + latest state association → SPI/CPX → Virtual ESP32 → TCP Host.

영상은 324×244 Mono8, 상태는 Body FLU velocity m/s, angular rate rad/s, Quaternion XYZW, EKF height, ToF, specific force입니다. 기존 Timestamp 및 Association 의미를 변경하지 않습니다. 세부 Wire Contract는 `virtual_aideck/docs/E2E_IMAGE_STATE_PROTOCOL.md`와 실제 `runtime/host_protocol` Decoder를 참조하십시오.

자체 Runtime은 virtual_aideck/runtime, Config는 virtual_aideck/config, Upstream Lock/Patch는 deps에 위치합니다. 외부 소스는 Installer가 생성하며 Git/ZIP에서 제외됩니다. Python 환경 Drone, SDK/Toolchain third_party, 빌드 runtime/build, 검증 로그 .local/verification은 로컬 생성물입니다.

Host Perception/Guidance/FSM은 포함하지 않습니다. 실제 비행 명령은 배포 검증에서 실행하지 않습니다.
