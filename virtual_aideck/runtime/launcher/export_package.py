"""Export only runtime sources/configuration, never validation or evidence.

--link-dependencies is a local reuse convenience, not a distributable SDK copy.
"""
import argparse,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(); p.add_argument('destination',type=Path); p.add_argument('--link-dependencies',action='store_true')
args=p.parse_args(); target=args.destination.resolve()
if target.exists(): raise SystemExit('Refusing to merge/overwrite destination')
target.mkdir(parents=True); va=target/'virtual_aideck'; va.mkdir()
shutil.copytree(ROOT/'virtual_aideck/runtime',va/'runtime',ignore=shutil.ignore_patterns('build','BUILD','__pycache__','*.pyc'))
shutil.copytree(ROOT/'virtual_aideck/config',va/'config')
shutil.copy2(ROOT/'virtual_aideck/run.sh',va/'run.sh')
for name in ['RUNTIME.md','E2E_IMAGE_STATE_PROTOCOL.md','E2E_OPERATION_HANDOFF.md']:
    source=ROOT/'virtual_aideck/docs'/name
    if source.exists():
        (va/'docs').mkdir(exist_ok=True);shutil.copy2(source,va/'docs'/name)
dependencies=['third_party','Drone','crazyflie-firmware','crazyflie-lib-python']
if args.link_dependencies:
    for name in dependencies: (target/name).symlink_to(ROOT/name,target_is_directory=True)
(va/'DEPENDENCIES.json').write_text(json.dumps(dict(required=dependencies,local_links=args.link_dependencies),indent=2)+'\n')
print(target)
