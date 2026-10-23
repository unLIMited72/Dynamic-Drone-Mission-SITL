#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
trap 'echo "INSTALL FAILED at line $LINENO" >&2' ERR
CHECK=0; ACCEPT=0; YES=0
for arg in "$@"; do
 case "$arg" in
 --check) CHECK=1;;
 --accept-unverified-license) ACCEPT=1;;
 --yes) YES=1;;
 --help) echo 'Usage: install.sh [--check] [--accept-unverified-license] [--yes]'; exit 0;;
 *) echo "Unknown option: $arg" >&2; exit 2;;
 esac
done
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 22.04 && "$(uname -m)" == x86_64 ]] || { echo 'Requires Ubuntu 22.04 x86_64'; exit 1; }
[[ -f /opt/ros/humble/setup.bash ]] || { echo 'ROS2 Humble prerequisite missing'; exit 1; }
# Native runtime requires no ROS workspace. Do not inherit Python paths from ROS.
unset PYTHONPATH PYTHONHOME
[[ "${ROS_DISTRO:-humble}" == humble ]] || { echo 'Conflicting ROS_DISTRO'; exit 1; }
missing=()
while IFS= read -r pkg; do
 [[ -z "$pkg" ]] && continue
 dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' || missing+=("$pkg")
done < "$ROOT/deps/apt-packages.txt"
if (( CHECK )); then
 printf 'Missing apt packages: %s\n' "${missing[*]:-none}"
 "$ROOT/scripts/bootstrap_external.sh" --check
 [[ -x "$ROOT/Drone/bin/python" ]]
 "$ROOT/Drone/bin/python" -c 'import mujoco,numpy,cflib; assert mujoco.__version__=="3.16.0"; print("MuJoCo",mujoco.__version__)'
 [[ -x "$ROOT/third_party/gap_riscv_toolchain/bin/riscv32-unknown-elf-gcc" ]]
 [[ -x "$ROOT/third_party/gap_sdk/install/workstation/bin/gvsoc_launcher" ]]
 "$ROOT/third_party/gap_sdk_venv/bin/python" -c 'from elftools.elf.elffile import ELFFile; print("SDK Python imports PASS")'
 (( ${#missing[@]} == 0 )); exit
fi
(( ACCEPT )) || { echo 'Required upstream drone-models has UNVERIFIED rights. Read docs/EXTERNAL_DEPENDENCIES.md; explicit --accept-unverified-license is required.'; exit 2; }
if (( ${#missing[@]} )); then
 printf 'System packages to install (GPU drivers are not changed): %s\n' "${missing[*]}"
 if (( ! YES )); then read -r -p 'Install these packages with sudo? [y/N] ' answer; [[ "$answer" == y ]] || exit 2; fi
 sudo apt-get update
 sudo apt-get install -y --no-install-recommends "${missing[@]}"
fi
"$ROOT/scripts/bootstrap_external.sh" --accept-unverified-license
python3 -m venv "$ROOT/Drone"
"$ROOT/Drone/bin/python" -m pip install -r "$ROOT/deps/runtime-requirements.txt"
"$ROOT/Drone/bin/python" -m pip install --no-build-isolation -e "$ROOT/crazyflie-lib-python"
python3 -m venv "$ROOT/third_party/gap_sdk_venv"
"$ROOT/third_party/gap_sdk_venv/bin/python" -m pip install -r "$ROOT/deps/sdk-requirements.txt"
"$ROOT/third_party/gap_sdk_venv/bin/python" "$ROOT/scripts/sdk_python_compat.py"
"$ROOT/Drone/bin/python" -m pip check
"$ROOT/third_party/gap_sdk_venv/bin/python" -m pip check
mkdir -p "$ROOT/.local/logs"
"$ROOT/scripts/build_sdk.sh" 2>&1 | tee "$ROOT/.local/logs/sdk-build.log"
"$ROOT/scripts/install.sh" --check
echo 'INSTALL COMPLETE; next: ./scripts/build.sh'
