"""Owned-process supervisor. Never sends a CRTP flight/arming command."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT/'virtual_aideck/runtime'
sys.path.insert(0,str(RUNTIME/'camera_input'))
from rotating import RotatingLog

def identity(pid):
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()
        return None if fields[0]=='Z' else fields[19]
    except (FileNotFoundError,ProcessLookupError): return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['start','foreground','status','logs','stop','_serve'])
    mode=p.add_mutually_exclusive_group(); mode.add_argument('--headless',action='store_true'); mode.add_argument('--gui',action='store_true')
    p.add_argument('--config',type=Path,default=ROOT/'virtual_aideck/config/runtime.json')
    args=p.parse_args(); cfg=json.loads(args.config.read_text())
    if args.command in ('start','foreground','_serve') and 'arena' in cfg:
        sys.path.insert(0,str(RUNTIME))
        from arena.config import resolve
        resolve(cfg['arena'])  # Reject invalid selection before build/process creation.
    state_dir=ROOT/cfg['state_dir']; state_dir.mkdir(parents=True,exist_ok=True)
    state_path=state_dir/'state.json'
    def read_state():
        try: return json.loads(state_path.read_text())
        except (FileNotFoundError,json.JSONDecodeError): return {}
    def alive(s): return bool(s.get('pid') and identity(s['pid'])==s.get('start_ticks'))
    current=read_state()
    if args.command=='status':
        current['supervisor_alive']=alive(current); print(json.dumps(current,indent=2)); return 0
    if args.command=='logs':
        if not current.get('log_dir'): print('No runtime log directory'); return 1
        for path in sorted(Path(current['log_dir']).glob('*.log')):
            print(f'--- {path.name} ---')
            print('\n'.join(path.read_text(errors='replace').splitlines()[-15:]))
        return 0
    if args.command=='stop':
        if not alive(current): print('Runtime is not running'); return 0
        os.kill(current['pid'],signal.SIGTERM)
        for _ in range(200):
            s=read_state()
            if not alive(s) or s.get('status') in ('stopped','failed'):
                print(json.dumps(s,indent=2)); return 0
            time.sleep(.1)
        print('Supervisor shutdown timed out; no unrelated process killed',file=sys.stderr); return 1
    if args.command=='start':
        if alive(current): print('Runtime already running',file=sys.stderr); return 2
        proc=subprocess.Popen([sys.executable,__file__,'_serve','--config',str(args.config.resolve()),
            '--gui' if args.gui else '--headless'],cwd=ROOT,start_new_session=True,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(1800):
            s=read_state()
            if s.get('pid')==proc.pid and s.get('status')=='running':
                print(json.dumps(s,indent=2)); return 0
            if proc.poll() is not None:
                print(json.dumps(read_state(),indent=2)); return proc.returncode or 1
            time.sleep(.1)
        os.kill(proc.pid,signal.SIGTERM); print('Startup timeout',file=sys.stderr); return 1

    lock=(state_dir/'runtime.lock').open('a+')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: return 2
    run_id=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+secrets.token_hex(3)
    out=ROOT/cfg['log_dir']/run_id; out.mkdir(parents=True)
    (out/'config_snapshot.json').write_text(json.dumps(cfg,indent=2)+'\n')
    state=dict(pid=os.getpid(),start_ticks=identity(os.getpid()),status='starting',run_id=run_id,
        log_dir=str(out),children={},exit_codes={},exit_records=[],session_history=[],automatic_flight_commands=False)
    stopping=False; children=[]; workers=[]; retired=set()
    ipc=tempfile.TemporaryDirectory(prefix='aideck-runtime-'); ipc_path=ipc.name+'/camera.sock'
    sys.path.insert(0,str(RUNTIME/'state_link'))
    from profile import configure, prepare_gvsoc
    firmware_binary=None
    def save():
        tmp=state_path.with_suffix('.tmp'); tmp.write_text(json.dumps(state,indent=2)+'\n'); os.replace(tmp,state_path)
        (out/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    save()
    def spawn(name,cmd,env=None,cwd=ROOT):
        proc=subprocess.Popen([str(x) for x in cmd],cwd=cwd,env=env,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True,text=True,bufsize=1)
        children.append((name,proc))
        state['children'][name]=dict(pid=proc.pid,start_ticks=identity(proc.pid)); save()
        def drain():
            with RotatingLog(out/(name+'.log')) as log:
                for line in proc.stdout: log.write(line)
            proc.stdout.close()
        thread=threading.Thread(target=drain,daemon=True); thread.start(); workers.append(thread)
        return proc
    def wait_ready(predicate,seconds=120):
        deadline=time.monotonic()+seconds
        while not predicate():
            if stopping: raise InterruptedError('stop requested')
            for name,proc in children:
                if proc.poll() is not None and name!='build' and proc not in retired: raise RuntimeError(f'{name} exited {proc.returncode}')
            if time.monotonic()>deadline: raise TimeoutError('readiness timeout')
            time.sleep(.1)
    def contains(name,text):
        path=out/(name+'.log'); return path.exists() and text in path.read_text(errors='replace')
    def build(session):
        proc=spawn('build',['bash',RUNTIME/'launcher/sdk.sh','build',session,str(cfg.get('session_us',3600000000))])
        wait_ready(lambda:proc.poll() is not None)
        if proc.returncode: raise RuntimeError('build failed')
    def launch_gv(session):
        prepare_gvsoc(cfg)
        env=os.environ.copy(); env.update(LIVE_CAMERA_SOCKET=ipc_path,LIVE_CAMERA_LIMIT='0')
        return spawn('gvsoc',['bash',RUNTIME/'launcher/sdk.sh','run',session,str(cfg.get('session_us',3600000000))],env)
    try:
        if not 1000000<=int(cfg.get('session_us',3600000000))<=3600000000: raise ValueError('session_us outside timer-safe range')
        if args.gui and not os.environ.get('DISPLAY'): raise RuntimeError('--gui requires DISPLAY; use --headless')
        if cfg['cpx_tcp_port']!=5000 or cfg['crtp_udp_port']!=cfg['firmware_udp_port']-100:
            raise ValueError('This profile requires TCP5000 and CRTP=firmware UDP minus100')
        for kind,port in [(socket.SOCK_STREAM,5000)]+[(socket.SOCK_DGRAM,cfg[k]) for k in
            ('camera_udp_port','firmware_udp_port','crtp_udp_port')]:
            with socket.socket(socket.AF_INET,kind) as check:
                if kind==socket.SOCK_STREAM: check.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                check.bind(('127.0.0.1',port))
        firmware_binary=configure(cfg,ipc_path,ROOT)
        session='0x'+secrets.token_hex(8); state['session']=session; save(); build(session)
        env=os.environ.copy(); env.pop('LD_PRELOAD',None); env.pop('LIVE_CAMERA_FAULTS',None)
        env.update(MUJOCO_GL='glfw' if args.gui else 'egl',LP_NUM_THREADS='2',PYTHONUNBUFFERED='1',
            PYTHONPATH=str(ROOT/'crazyflie-lib-python'))
        py=ROOT/'Drone/bin/python'; camera=RUNTIME/'camera_input'
        spawn('adapter',[py,camera/'adapter.py','--port',cfg['camera_udp_port'],'--socket',ipc_path,'--log',out/'adapter.jsonl'],env)
        source_cmd = [py, camera / 'source.py', '--session', session, '--fps', cfg['source_sim_fps'], '--port', cfg['firmware_udp_port'],
                      '--camera-port', cfg['camera_udp_port'], '--log', out / 'source.jsonl',]
        if 'arena' in cfg: source_cmd.extend(['--arena-config',out/'config_snapshot.json'])
        if cfg.get('flowdeck', False): source_cmd.append('--flowdeck') # Flow Deck 활성화 여부
        if args.gui: source_cmd.append('--gui') # MuJoCo GUI 활성화 여부
        spawn('source', source_cmd, env)
        spawn('firmware',[firmware_binary,cfg['firmware_udp_port']],env,out)
        wait_ready(lambda:contains('source','firmware connected'))
        gv=launch_gv(session)
        wait_ready(lambda:contains('gvsoc','VESP32_TCP_LISTEN') and contains('gvsoc','LIVE_EMIT_COMPLETE'))
        state['status']='running'; state['tcp']='127.0.0.1:5000'; state['crtp']=f"udp://127.0.0.1:{cfg['crtp_udp_port']}"; save()
        while not stopping:
            for name,proc in children:
                if name=='build' or proc is not gv and name=='gvsoc': continue
                if proc.poll() is not None:
                    if proc is gv and proc.returncode==0 and contains('gvsoc','RUNTIME_SESSION_ROTATE'):
                        # Restart only our camera/ESP32 VM; CRTP physics remains independent.
                        state['status']='rotating'; save()
                        state['session_history'].append(dict(session=session,pid=proc.pid,exit_code=proc.returncode))
                        retired.add(proc)
                        if Path(ipc_path).exists(): Path(ipc_path).unlink()
                        session='0x'+secrets.token_hex(8); build(session); gv=launch_gv(session)
                        state['session']=session; state['status']='running'; save(); break
                    raise RuntimeError(f'{name} exited unexpectedly: {proc.returncode}')
            time.sleep(.1)
    except InterruptedError: pass
    except Exception as error:
        state['error']=str(error); state['status']='failed'; save()
    finally:
        for name,proc in reversed(children):
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(proc.pid,signal.SIGKILL); proc.wait()
            state['exit_codes'].setdefault(name,proc.returncode)
            state['exit_records'].append(dict(name=name,pid=proc.pid,exit_code=proc.returncode))
        for thread in workers: thread.join(timeout=2)
        ipc.cleanup()
        if state['status']!='failed': state['status']='stopped'
        save()
    return 1 if state['status']=='failed' else 0

if __name__=='__main__': raise SystemExit(main())
