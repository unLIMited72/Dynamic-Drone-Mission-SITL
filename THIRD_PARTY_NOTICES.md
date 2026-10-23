# License and third-party notices

자체 작성 Runtime, Arena, 배포 스크립트 및 권한을 확인한 Arena Assets는 GPL-3.0 조건입니다. 루트 LICENSE를 참조하십시오. 이는 외부 의존성의 라이선스를 변경하지 않습니다.

외부 소스는 설치 시 원본 저장소에서 가져옵니다. URL, 고정 Commit, 원본 고지와 미확인 권한은 [External dependencies](docs/EXTERNAL_DEPENDENCIES.md)에 기록합니다.

`deps/patches/simulator.patch`는 llanesc/crazyflie-simulation의 MIT 소스에 적용됩니다. 원본 MIT LICENSE를 deps/licenses/simulator-LICENSE에 보존합니다. `deps/patches/gap-sdk.patch`는 GreenWaves gap_sdk의 Apache-2.0 및 파일별 고지를 유지합니다. SDK 원본 LICENSE를 deps/licenses/gap-sdk-LICENSE에 보존합니다. 설치된 원본 파일의 저작권 고지는 삭제하지 않습니다.

MuJoCo와 Python 패키지는 pip에서 별도로 설치되며 해당 패키지 고지가 적용됩니다. 본 ZIP은 외부 바이너리를 재배포하지 않습니다. UPSTREAM_ONLY는 권한 승인 상태가 아닙니다. drone-models는 MIT_DECLARED_LICENSE_FILE_MISSING 상태입니다. pyproject/PyPI의 MIT 선언을 확인했지만 원문과 개별 Asset 범위는 별도 확인 대상으로 남습니다. 후속 Crazyflow LICENSE의 자동 소급 적용을 주장하지 않습니다.
