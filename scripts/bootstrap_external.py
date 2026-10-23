#!/usr/bin/env python3
"""Pinned upstream-only dependencies. Refuse unexpected repositories/edits."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'deps/external_repositories.lock.json'
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def git(dest,*args):return subprocess.check_output(['git','-C',str(dest),*args],text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--accept-unverified-license',action='store_true');a=p.parse_args()
 rows=json.loads(LOCK.read_text())['repositories'];receipts=[]
 for dep in rows:
  url=dep['repository'];commit=dep['commit'];dest=(ROOT/dep['destination']).resolve()
  if not dest.is_relative_to(ROOT) or not url.startswith('https://github.com/') or not url.endswith('.git') or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise ValueError('Invalid dependency lock entry')
  if dep['license_status']=='UNVERIFIED':
   print('UNVERIFIED usage/modification rights:',dep['name'],'; upstream clone grants no license.',flush=True)
   if not a.check and not a.accept_unverified_license:raise SystemExit('Explicit --accept-unverified-license required; this acknowledges risk, not permission.')
  patch=ROOT/dep['patch'] if dep.get('patch') else None
  if patch and digest(patch)!=dep['patch_sha256']:raise SystemExit('Patch hash mismatch')
  if dest.exists() and any(dest.iterdir()):
   if not (dest/'.git').exists() or git(dest,'rev-parse','HEAD')!=commit or git(dest,'remote','get-url','origin')!=url:raise SystemExit('Protecting unexpected existing dependency: '+str(dest))
   untracked=git(dest,'ls-files','--others','--exclude-standard')
   if untracked:raise SystemExit('Protecting untracked dependency files: '+str(dest))
   expected=patch.read_text().strip() if patch else ''
   actual=git(dest,'diff','--binary','--ignore-submodules=all')
   if actual!=expected:raise SystemExit('Protecting modified dependency: '+str(dest))
  elif a.check:raise SystemExit('Missing dependency: '+dep['name'])
  else:
   dest.parent.mkdir(parents=True,exist_ok=True)
   temp=Path(tempfile.mkdtemp(prefix='.'+dep['name']+'-',dir=dest.parent))
   run(['git','init','-q',str(temp)]);run(['git','-C',str(temp),'remote','add','origin',url])
   run(['git','-C',str(temp),'fetch','--depth','1','origin',commit]);run(['git','-C',str(temp),'checkout','--detach','FETCH_HEAD'])
   assert git(temp,'rev-parse','HEAD')==commit
   if patch:run(['git','-C',str(temp),'apply','--check',str(patch)]);run(['git','-C',str(temp),'apply',str(patch)])
   if dest.exists():dest.rmdir() # only verified empty placeholder
   temp.rename(dest)
  receipts.append(dict(name=dep['name'],url=url,head=git(dest,'rev-parse','HEAD'),patch=dep.get('patch'),license_status=dep['license_status']))
  print('VERIFIED',dep['name'],commit,flush=True)
 if not a.check:
  out=ROOT/'.local';out.mkdir(exist_ok=True);(out/'external_receipt.json').write_text(json.dumps(receipts,indent=2))
if __name__=='__main__':main()
