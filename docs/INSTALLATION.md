# 설치와 실행

대상: Ubuntu 22.04.5 LTS x86_64, Python 3.10, ROS2 Humble 설치 완료, 인터넷 및 필요시 sudo. Native 실행은 ROS Workspace를 빌드하지 않습니다. 새 VM 전체 설치 및 다른 GPU 호환성은 아직 검증되지 않았습니다. CPU/RAM/디스크 최소 사양은 확정하지 않았습니다. SDK/Toolchain/빌드 공간이 추가로 필요합니다.

```bash
cat /etc/os-release
uname -m
test -f /opt/ros/humble/setup.bash
git clone https://github.com/unLIMited72/Dynamic-Drone-Mission-SITL.git
cd Dynamic-Drone-Mission-SITL
./scripts/install.sh --check
```

첫 `--check`에서 미설치 의존성 오류가 발생하는 것은 정상입니다. 외부 권한 고지를 먼저 읽으십시오. 설치는 누락 apt 패키지를 표시하고 확인 후 설치하며 GPU Driver는 변경하지 않습니다.

```bash
./scripts/install.sh --accept-unverified-license
./scripts/build.sh
./scripts/verify.sh --smoke
./scripts/verify.sh --e2e --scenario all --seconds 30
./virtual_aideck/run.sh start --gui
./virtual_aideck/run.sh status
./virtual_aideck/run.sh logs
./virtual_aideck/run.sh stop
```

디스플레이 없는 환경에서는 `start --headless`를 사용합니다. 설치 스크립트는 자신의 경로에서 프로젝트 루트를 구합니다. 새 사용자 홈에서도 서버 경로를 수정할 필요가 없습니다. ZIP은 해제 후 프로젝트 루트에서 같은 명령을 사용합니다. ZIP에 `.git`은 필요하지 않으며 외부 저장소 다운로드용 git은 필요합니다. 게시된 Release가 없는 경우 ZIP 다운로드 링크는 제공하지 않습니다.

경기장은 `start --headless --config virtual_aideck/config/arena_mission3.json`처럼 선택합니다. Basic이 기본값입니다. [설정](CONFIGURATION.md)을 참조하십시오. TCP5000 Host Decoder는 `virtual_aideck/runtime/host_protocol/e2e_client.py`입니다. 외부 시험 프로젝트의 독립 Live Viewer는 배포하지 않으며 Runtime의 `host_protocol/preview.py`를 유지합니다.

반복 설치는 고정 의존성을 확인합니다. 사용자 변경이 있으면 덮어쓰지 않습니다. 업그레이드 시 Runtime을 정상 종료하고 변경을 백업한 후 새 디렉터리에 새 버전을 설치하십시오. 실패한 설치를 삭제하는 자동 clean 기능은 없습니다. SDK 가상환경의 Python 3.10 호환 처리는 `sdk_python_compat.py`에 명시합니다. FTDI/Flasher는 Native Runtime에 불필요하여 빌드하지 않습니다.

개발 서버 신규 디렉터리 검증과 Fresh Ubuntu 검증은 다릅니다. 실제 결과는 배포 보고서를 따르며 모든 PC의 GUI/20fps를 보장하지 않습니다. 자세한 실패 대응은 [Troubleshooting](TROUBLESHOOTING.md)을 참조하십시오.
