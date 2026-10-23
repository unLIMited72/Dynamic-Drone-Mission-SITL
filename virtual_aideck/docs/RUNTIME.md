# v1.0.0 Runtime 운영

프로젝트 최상위 폴더에서 실행합니다. 기본 설정은 Basic이며 자동 이륙/비행 명령은 없습니다.

```bash
./virtual_aideck/run.sh start --gui
./virtual_aideck/run.sh status
./virtual_aideck/run.sh logs
./virtual_aideck/run.sh stop
```

Display 없는 환경에서는 `start --headless`를 사용합니다. GUI는 OpenGL, Headless는 EGL이 필요합니다. `stop`은 Supervisor 및 자신이 소유한 자식 프로세스를 종료하며 Landing 명령이 아닙니다. 다른 사용자의 Runtime이나 TCP Consumer를 종료하지 않습니다.

Arena 선택은 시작 시 읽습니다. 기존 실행을 stop한 뒤 완성된 프로파일을 사용하고 이후 lifecycle 명령에도 같은 Config를 지정합니다.

```bash
./virtual_aideck/run.sh start --headless --config virtual_aideck/config/arena_mission3.json
./virtual_aideck/run.sh status --config virtual_aideck/config/arena_mission3.json
./virtual_aideck/run.sh logs --config virtual_aideck/config/arena_mission3.json
./virtual_aideck/run.sh stop --config virtual_aideck/config/arena_mission3.json
```

- [초보자 설치 및 실행](../../README.md)
- [설정: 5개 Arena, Rover Mode/Speed, 포트](../../docs/CONFIGURATION.md)
- [상세 설치·업데이트](../../docs/INSTALLATION.md)
- [문제 해결](../../docs/TROUBLESHOOTING.md)
- [Host Camera/State Wire Contract](E2E_IMAGE_STATE_PROTOCOL.md)
- [Host PC 개발 인계](../../docs/HOST_PC_DEVELOPMENT_HANDOFF.md)

기존 TCP5000은 영상+상태 단일 Consumer를 사용합니다. CRTP UDP20050은 별도 명령 경로입니다. 직접 작성할 Host 수신기에 기존 Decoder를 재사용하세요. 외부 Live Viewer/Archive는 설치 또는 운영 의존성이 아닙니다.

검증은 자신이 실행 중인 Runtime을 정상 종료한 뒤 `./scripts/verify.sh --smoke` 또는 `./scripts/verify.sh --e2e --scenario all --seconds 60`으로 실행합니다. 결과는 `.local/verification/`, Runtime 로그는 `virtual_aideck/runtime_logs/`, 빌드 로그는 `.local/logs/`에 기록됩니다. 무결성 결과와 FPS를 분리합니다.
