# Troubleshooting

| 증상 | 확인/조치 |
|---|---|
| git 미설치/Clone 실패 | Ubuntu git 설치, 네트워크와 Lock의 공식 URL 접근 확인. gh는 팀원 설치에 필수 아님 |
| Submodule/외부 소스 누락 | install.sh 사용. ZIP에도 독립 Bootstrap 적용. 임의 최신 Commit으로 대체 금지 |
| 기존 저장소 수정 오류 | 사용자 변경 보존. 별도 새 디렉터리에서 설치, reset/clean 금지 |
| pip 충돌/MuJoCo Import | Drone/bin/python -m pip check, install.sh 재검증. 시스템 pip/기존 서버 venv 사용 금지 |
| GAP8 SDK/RISC-V 누락 | bootstrap --check와 Lock HEAD 확인 후 install. PATH 수동 서버 경로 연결 금지 |
| Firmware Build 실패 | .local/logs 및 runtime/build 기록 확인. 불완전 빌드는 보존 후 별도 디렉터리 재현 |
| ELF MutableMapping 오류 | scripts/sdk_python_compat.py 설치 단계 누락 여부 확인 |
| GLFW/DISPLAY/GUI 오류 | 로컬 Display/X11/Wayland 및 GPU Driver 확인. 원격 SSH에서는 headless 사용 |
| EGL/OpenGL/llvmpipe | Mesa/EGL 또는 제조사 Driver 확인. llvmpipe는 CPU rendering으로 성능 저하 가능 |
| NVIDIA 오류 | 설치된 Driver와 OpenGL/EGL 일치 확인. Installer는 Driver를 교체하지 않음 |
| Port already in use | run.sh status 및 ss 확인. 다른 사용자의 프로세스 종료 금지 |
| TCP5000 연결 실패 | Runtime status/logs에서 ESP32/GAP8 시작 확인, 단일 Consumer 충돌 확인 |
| UART Decode/CRC 오류 | Native 로그 보존, state_link 및 고정 버전 확인. 프로토콜을 바꿔 우회 금지 |
| Camera FPS 미달 | CPU/GPU 부하, software rendering, 실행별 FPS 기록 확인. 20fps 미달 기록 보존 |

```bash
./virtual_aideck/run.sh status
./virtual_aideck/run.sh logs
./virtual_aideck/run.sh stop
```

자신이 시작한 Runtime만 stop하십시오. Verify는 점유 포트를 검사하고 해당 시험을 중단합니다. 테스트에서 ARM/Takeoff/Land를 자동 실행하지 않습니다. 실패 로그/결과는 삭제하지 말고 재현 명령과 함께 보존하십시오.
