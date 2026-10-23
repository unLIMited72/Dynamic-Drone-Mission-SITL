"""Scoped Python 3.10 compatibility for pinned pyelftools 0.24 in SDK venv."""
import sysconfig
from pathlib import Path
p = Path(sysconfig.get_path('purelib'))
module = p / 'mission_sdk_compat.py'
content = '''import collections
import collections.abc
for name in ('MutableMapping', 'Mapping', 'MutableSequence', 'Sequence', 'Iterable', 'Callable'):
    if not hasattr(collections, name):
        setattr(collections, name, getattr(collections.abc, name))
'''
if module.exists() and module.read_text() != content:
    raise SystemExit('Refusing to overwrite modified SDK compatibility module')
module.write_text(content)
(p / 'mission_sdk_compat.pth').write_text('import mission_sdk_compat\n')
