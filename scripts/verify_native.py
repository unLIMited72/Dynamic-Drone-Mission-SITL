"""Own-process native runtime test with original payload comparisons; no flight commands."""
import argparse,json,time,socket,subprocess,struct,re,sys,uuid
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'virtual_aideck/runtime/host_protocol'))
from e2e_client import Client
NAMES=('basic','integrated','mission1','mission2','mission3','mission3_straight')
def run_one(name,seconds,gui):
 for port,kind in [(5000,socket.SOCK_STREAM),(20150,socket.SOCK_DGRAM),(20050,socket.SOCK_DGRAM),(15200,socket.SOCK_DGRAM)]:
  with socket.socket(socket.AF_INET,kind) as sock:
   try:sock.bind(('127.0.0.1',port))
   except OSError:raise RuntimeError(f'BLOCKED: port {port} occupied; no process stopped')
 out=R/'.local/verification'/('native_'+name+'_'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 cfg=json.loads((R/'virtual_aideck/config'/('runtime.json' if name=='basic' else 'arena_'+name+'.json')).read_text())
 cfg['state_link']['sender_trace']=str(out/'sender.bin');config=out/'config.json';config.write_text(json.dumps(cfg,indent=2))
 def command(action,*args):return subprocess.run([str(R/'virtual_aideck/run.sh'),action,*args,'--config',str(config)],capture_output=True,text=True,timeout=240)
 started=False;client=None;records=[];state={};error=None
 try:
  proc=command('start','--gui' if gui else '--headless');(out/'start.log').write_text(proc.stdout+proc.stderr)
  if proc.returncode:raise RuntimeError('Runtime start failed; inspect '+str(out/'start.log'))
  started=True;state=json.loads(proc.stdout)
  import cflib.crtp
  from cflib.crazyflie import Crazyflie
  from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
  cflib.crtp.init_drivers()
  with SyncCrazyflie('udp://127.0.0.1:20050',cf=Crazyflie()) as cf:
   deadline=time.monotonic()+20
   while not cf.cf.param.is_updated:
    if time.monotonic()>deadline:raise TimeoutError('Parameter read')
    time.sleep(.02)
   assert int(cf.cf.param.get_value('stabilizer.estimator'))==2 and int(cf.cf.param.get_value('stabilizer.controller'))==1
  client=Client(timeout=20)
  for _ in range(10):client.receive()
  start=time.monotonic()
  while time.monotonic()-start<seconds:records.append(client.receive()[0])
  assert client.errors==0
 except BaseException as exc:error=repr(exc)
 finally:
  if client:client.close()
  if started:
   proc=command('stop');(out/'stop.log').write_text(proc.stdout+proc.stderr)
 (out/'records.json').write_text(json.dumps(records))
 if error:raise RuntimeError(error)
 assert len(records)>=2
 fps=(len(records)-1)/(records[-1]['wall']-records[0]['wall'])
 gaps=sum(max(0,b['frame_sequence']-a['frame_sequence']-1) for a,b in zip(records,records[1:]))
 trace=(out/'sender.bin').read_bytes();counts=struct.unpack_from('<5I',trace);produced={};sent={}
 for table,n,offset in [(produced,counts[0],64),(sent,counts[1],64+20000*136)]:
  for i in range(min(n,20000)):
   payload=trace[offset+i*136:offset+(i+1)*136];table[struct.unpack_from('<QQ',payload,8)]=payload.hex()
 log=Path(state['log_dir']);source=set()
 for p in log.glob('source.jsonl*'):
  for line in p.read_text().splitlines():
   try:x=json.loads(line)
   except ValueError:continue
   if 'sha256' in x:source.add(x['sha256'])
 gv='\n'.join(p.read_text(errors='replace') for p in log.glob('gvsoc.log*'))
 latches={int(i):h for i,h in re.findall(r'LIVE_LATCH index=(\d+) session=\d+ seq=\d+ sha256=([0-9a-f]{64})',gv)}
 matches=valid=0
 for record in records:
  a=record['association'];assert a and a['state_available'];e=a['ego_state'];key=(e['stm32_boot_id'],e['state_sequence'])
  assert produced.get(key)==sent.get(key)==a['payload_hex'];matches+=1;valid+=bool(a['state_association_valid'])
  assert record['sha256'] in source and latches[record['frame_sequence']]==record['sha256']
 clean=re.sub(r'(?:LIVE_|VESP32_)[^\n]*\n','',gv)
 counters=[]
 for line in clean.splitlines():
  if 'EGO_STATS ' in line:
   c={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line.split('EGO_STATS ',1)[1])}
   if all(k in c for k in ('frames','crc','decode','gaps')):counters.append(c)
 assert counters and counters[-1]['crc']==0 and counters[-1]['decode']==0 and gaps==0 and valid/len(records)>=.99
 result=dict(scenario=name,gui=gui,seconds=seconds,frames=len(records),fps=fps,match_ratio=matches/len(records),valid_ratio=valid/len(records),gaps=gaps,integrity='PASS',strict_20fps='PASS' if fps>=20 else 'FAIL',gap8=counters[-1],runtime_logs=str(log))
 (out/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scenario',choices=('all',*NAMES),default='basic');p.add_argument('--seconds',type=float,default=60);p.add_argument('--gui',action='store_true');a=p.parse_args()
 if not 5<=a.seconds<=180:raise SystemExit('seconds must be 5..180')
 results=[run_one(n,a.seconds,a.gui) for n in (NAMES if a.scenario=='all' else (a.scenario,))]
