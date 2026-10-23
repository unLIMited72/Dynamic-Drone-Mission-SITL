"""Source-only checks; this is not Native E2E qualification."""
import ast, hashlib, json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
for base in ('scripts','virtual_aideck/runtime'):
 for p in (R/base).rglob('*.py'):
  if not any(x in p.parts for x in ('build','__pycache__')):ast.parse(p.read_text(),filename=str(p))
for p in (R/'virtual_aideck/config').glob('*.json'):json.loads(p.read_text())
lock=json.loads((R/'deps/external_repositories.lock.json').read_text())
for row in lock['repositories']:
 assert len(row['commit'])==40 and row['repository'].startswith('https://github.com/')
 if row['patch']:assert hashlib.sha256((R/row['patch']).read_bytes()).hexdigest()==row['patch_sha256']
assets=json.loads((R/'deps/arena_assets.sha256.json').read_text())
for rel,sha in assets.items():assert hashlib.sha256((R/rel).read_bytes()).hexdigest()==sha,rel
print('Source syntax, JSON, patch and Arena asset hashes PASS; Native E2E NOT_RUN')
