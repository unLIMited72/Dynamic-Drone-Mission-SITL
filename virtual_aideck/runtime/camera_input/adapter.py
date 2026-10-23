import argparse
import json
import select
import signal
import socket
import time
from pathlib import Path
from wire import Assembler,IPC
from rotating import RotatingLog

def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=15200)
    p.add_argument('--socket',required=True); p.add_argument('--log',type=Path,required=True)
    args=p.parse_args(); running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop)
    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); udp.bind(('127.0.0.1',args.port)); udp.setblocking(False)
    udp.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,512*1024)
    conn=None; pending=None; assembly=Assembler(); replaced=0
    with RotatingLog(args.log) as log:
        print('LIVE_ADAPTER_READY',flush=True)
        while running:
            if conn is None:
                candidate=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
                candidate.setblocking(False)
                try: candidate.connect(args.socket); conn=candidate
                except OSError: candidate.close()
            ready,_,_=select.select([udp],[],[],.002)
            if ready:
                for _ in range(32):
                    try: packet=udp.recv(65536)
                    except BlockingIOError: break
                    frame=assembly.feed(packet)
                    if frame is not None:
                        session,seq,sim_ns,digest=IPC.unpack_from(frame)
                        if pending is not None:
                            replaced+=1
                            log.write(json.dumps(dict(event='pending_drop',seq=IPC.unpack_from(pending)[1]))+'\n')
                        pending=frame
                        log.write(json.dumps(dict(event='accepted',seq=seq,session=session,sha256=digest.hex(),host_monotonic=time.monotonic()))+'\n')
            assembly.expire()
            if pending is not None and conn is not None:
                try:
                    count=conn.send(pending)
                    if count!=len(pending): raise RuntimeError('partial seqpacket send')
                    log.write(json.dumps(dict(event='forwarded',seq=IPC.unpack_from(pending)[1],host_monotonic=time.monotonic()))+'\n')
                    pending=None
                except BlockingIOError: pass
                except (BrokenPipeError,ConnectionResetError): conn.close(); conn=None
        log.write(json.dumps(dict(event='summary',accepted=assembly.accepted,incomplete_drops=assembly.dropped,
            invalid=assembly.invalid,pending_replaced=replaced))+'\n')
    if conn: conn.close()
    udp.close()

if __name__=='__main__': main()
