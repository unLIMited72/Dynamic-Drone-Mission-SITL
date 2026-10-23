"""Live-only source protocol. Legacy CameraRenderer UDP remains unchanged."""
import hashlib
import struct
import time

WIDTH,HEIGHT,SIZE,CHUNK=324,244,79056,60000
UDP=struct.Struct('<4sB3xQQQHHHHI32s')
IPC=struct.Struct('<QQQ32s')

def encode(session,seq,sim_ns,pixels):
    if len(pixels)!=SIZE: raise ValueError('image size')
    digest=hashlib.sha256(pixels).digest()
    return [UDP.pack(b'LVC1',1,session,seq,sim_ns,i,2,WIDTH,HEIGHT,SIZE,digest)+pixels[i*CHUNK:(i+1)*CHUNK] for i in range(2)]

class Assembler:
    def __init__(self):
        self.current=None; self.parts={}; self.last=-1; self.session=None
        self.started=0; self.accepted=0; self.dropped=0; self.invalid=0
    def discard(self):
        if self.current is not None: self.dropped+=1
        self.current=None; self.parts={}
    def expire(self,now=None):
        if self.current is not None and (time.monotonic() if now is None else now)-self.started>.25:
            self.discard()
    def feed(self,packet,now=None):
        now=time.monotonic() if now is None else now
        self.expire(now)
        if len(packet)<UDP.size: self.invalid+=1; return None
        magic,version,session,seq,sim_ns,index,total,w,h,size,digest=UDP.unpack_from(packet)
        payload=packet[UDP.size:]
        if (magic,version,total,w,h,size)!=(b'LVC1',1,2,WIDTH,HEIGHT,SIZE) or index>=2 or len(payload)!=(CHUNK if index==0 else SIZE-CHUNK):
            self.invalid+=1; self.discard(); return None
        if self.session is None: self.session=session
        if session!=self.session or seq<=self.last:
            self.invalid+=1; return None
        key=(session,seq,sim_ns,digest)
        if self.current is not None and self.current!=key:
            if seq<=self.current[1]: self.invalid+=1; return None
            self.discard()
        if self.current is None: self.current=key; self.started=now
        if index in self.parts:
            self.invalid+=1; self.last=seq; self.discard(); return None
        self.parts[index]=payload
        if len(self.parts)<2: return None
        pixels=self.parts[0]+self.parts[1]
        self.current=None; self.parts={}; self.last=seq
        if hashlib.sha256(pixels).digest()!=digest:
            self.invalid+=1; self.dropped+=1; return None
        self.accepted+=1
        return IPC.pack(session,seq,sim_ns,digest)+pixels
