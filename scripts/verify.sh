#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:---check}"; (( $# == 0 )) || shift
case "$MODE" in
 --check) exec "$ROOT/scripts/install.sh" --check;;
 --build) exec "$ROOT/scripts/build.sh";;
 --smoke) unset PYTHONPATH PYTHONHOME; export MUJOCO_GL=egl; exec "$ROOT/Drone/bin/python" "$ROOT/scripts/smoke.py" "$@";;
 --e2e) unset PYTHONPATH PYTHONHOME; exec "$ROOT/Drone/bin/python" "$ROOT/scripts/verify_native.py" "$@";;
 --help) echo 'Usage: verify.sh --check|--build|--smoke|--e2e [--scenario all|basic|integrated|mission1|mission2|mission3|mission3_straight] [--seconds 60] [--gui]';;
 *) echo "Unknown mode: $MODE" >&2; exit 2;;
esac
