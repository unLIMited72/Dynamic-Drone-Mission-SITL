"""Opt-in CameraRenderer transport wrapper; no physics/renderer substitutions."""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import threading
import time
import wire
from rotating import RotatingLog

ROOT=Path(__file__).resolve().parents[3]
SIM=ROOT/'crazyflie-firmware/tools/crazyflie-simulation/simulator_files/mujoco'
sys.path.insert(0,str(SIM))
import crazysim

class FrameSocket:
    def __init__(self,port,session,log):
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.port=port; self.session=session; self.log=log; self.seq=0
        self.parts={}; self.sim_ns=0; self.started=0
    def sendto(self,packet,dest):
        index,total,w,h=struct.unpack_from('<HHHH',packet)
        if index==0: self.parts={}
        assert (total,w,h)==(2,324,244)
        self.parts[index]=packet[8:]
        if len(self.parts)!=2: return len(packet)
        pixels=self.parts[0]+self.parts[1]; errors=0
        packets=wire.encode(self.session,self.seq,self.sim_ns,pixels)
        fault=None
        for data in packets:
            try: self.sock.sendto(data,('127.0.0.1',self.port))
            except BlockingIOError: errors+=1
        self.log.write(json.dumps(dict(event='source',session=self.session,seq=self.seq,
            sim_ns=self.sim_ns,host_monotonic=time.monotonic(),sha256=hashlib.sha256(pixels).hexdigest(),
            render_and_pack_s=time.monotonic()-self.started,send_errors=errors,fault=fault))+'\n'); self.log.flush()
        self.seq+=1; self.parts={}
        return len(packet)
    def close(self): self.sock.close()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=20150)
    p.add_argument('--camera-port',type=int,default=15200); p.add_argument('--fps',type=float,default=30)
    p.add_argument('--session',required=True); p.add_argument('--log',type=Path,required=True)
    p.add_argument('--gui',action='store_true')
    p.add_argument('--arena-config',type=Path)
    p.add_argument('--flowdeck', action='store_true')
    args=p.parse_args(); log=RotatingLog(args.log)
    original=crazysim.CameraRenderer
    renderers=[]
    class LiveRenderer(original):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            renderers.append(self)
            self._sock.close(); self._sock=FrameSocket(args.camera_port,int(args.session,0),log)
            from OpenGL.GL import glGetString,GL_RENDERER,GL_VERSION
            print('LIVE_OPENGL',glGetString(GL_RENDERER),glGetString(GL_VERSION),flush=True)
        def maybe_render(self,model,data,dt):
            self._sock.sim_ns=round(data.time*1e9)
            self._sock.started=time.monotonic()
            return super().maybe_render(model,data,dt)
    crazysim.CameraRenderer=LiveRenderer
    def close_renderers():
        for renderer in renderers:
            renderer._renderer.close()
            renderer._sock.close()
    if args.gui:
        # Release offscreen GL resources while GLFW/viewer is still alive.
        # The upstream renderer only closes its UDP socket, leaving GL teardown
        # to Python finalizers after the viewer has destroyed its context.
        original_viewer=crazysim.mujoco.viewer.launch_passive
        @contextmanager
        def owned_viewer(*a,**kw):
            before=set(threading.enumerate()); owned=[]
            try:
                with original_viewer(*a,**kw) as viewer:
                    # Installed MuJoCo launch_passive starts a daemon render
                    # thread; Handle.close requests exit but does not join it.
                    owned=[t for t in threading.enumerate() if t not in before and
                           getattr(t,'_target',None) is crazysim.mujoco.viewer._launch_internal]
                    try: yield viewer
                    finally: close_renderers()
            finally:
                for thread in owned:
                    thread.join(timeout=3)
                    if thread.is_alive(): raise RuntimeError('owned viewer shutdown timeout')
                print(f'LIVE_VIEWER_THREADS_JOINED count={len(owned)}',flush=True)
        crazysim.mujoco.viewer.launch_passive=owned_viewer
    scene_args={}
    if args.arena_config:
        sys.path.insert(0,str(ROOT/'virtual_aideck/runtime'))
        from arena.config import resolve
        from arena.model_builder import build
        from arena.rover_adapter import initialize
        config=resolve(json.loads(args.arena_config.read_text())['arena'])
        scene=build(config,args.log.parent/'arena')
        scene_args=dict(scene_path=str(scene),scene_initializer=lambda m,d:initialize(m,d,config))
        print('ARENA_CONFIG',json.dumps(config),flush=True)
    sim=crazysim.CrazySimMuJoCo(model_path=str(SIM/crazysim.MODEL_PATHS[crazysim.DEFAULT_MODEL_TYPE]),
        host='127.0.0.1',base_port=args.port,spawn_positions=[(0,0)],visualize=args.gui,
        flowdeck=args.flowdeck,camera_enabled=True,cam_fps=args.fps,cam_port=args.camera_port,**scene_args)
    signal.signal(signal.SIGTERM,lambda *_: setattr(sim,'_running',False))
    try: sim.run()
    finally:
        close_renderers()
        log.close()

if __name__=='__main__': main()
