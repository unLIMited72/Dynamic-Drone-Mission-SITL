"""Private GVSoC module search tree: never write installed SDK."""
import sys
from pathlib import Path
source,target=map(Path,sys.argv[1:]);target.mkdir(exist_ok=True)
for p in source.iterdir():
    dst=target/p.name
    if not dst.exists():dst.symlink_to(p.resolve(),target_is_directory=p.is_dir())
