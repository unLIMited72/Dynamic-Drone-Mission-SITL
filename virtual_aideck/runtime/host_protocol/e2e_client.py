"""Image + native GAP8-latched state over the existing single TCP endpoint."""
import argparse, hashlib, json, socket, struct, time
from collections import deque
from pathlib import Path
from client import packet, metadata, ProtocolError
from frame_state import decode_state, Matcher

class Client:
    def __init__(self,host='127.0.0.1',port=5000,timeout=20):
        self.sock=socket.create_connection((host,port),timeout)
        self.matcher=Matcher();self.ready=deque();self.begin=None;self.pixels=None
        self.header=False;self.previous=None;self.errors=0
    def close(self): self.sock.close()
    def receive(self):
        while not self.ready:
            body=packet(self.sock)
            # Image chunks can begin with any byte; only recognize envelope when
            # outside pixel transfer. Sender never interleaves state with pixels.
            if self.begin is None and body[:1]==b'\xbe':
                try: row=decode_state(body)
                except ProtocolError:
                    self.errors+=1;continue
                self.ready.extend(self.matcher.add(row)); continue
            if self.begin is None:
                self.begin=metadata(body,1);self.header=True;self.pixels=bytearray();continue
            if self.header:
                if body!=struct.pack('<BHHBBI',0xbc,324,244,1,0,79056):raise ProtocolError('image header')
                self.header=False;continue
            if len(self.pixels)<79056:
                if not body or len(self.pixels)+len(body)>79056:raise ProtocolError('image bounds')
                self.pixels.extend(body);continue
            end=metadata(body,2);end['kind']=1
            if end!=self.begin:raise ProtocolError('image begin/end mismatch')
            signature=2166136261
            for i in range(244):signature=((signature^self.pixels[i*324])*16777619)&0xffffffff
            if signature!=end['image_signature']:raise ProtocolError('pixel signature')
            if self.previous and self.previous['session_id']==end['session_id']:
                gap=end['frame_sequence']-self.previous['frame_sequence']-1
                if gap<0:raise ProtocolError('image duplicate/backwards')
                self.matcher.stats['image_gaps']+=gap
                if end['gap8_capture_end_tick_us']<=self.previous['gap8_capture_end_tick_us']:raise ProtocolError('capture backwards')
            self.previous=end
            row=dict(end,sha256=hashlib.sha256(self.pixels).hexdigest(),wall=time.monotonic())
            self.ready.extend(self.matcher.add(row,bytes(self.pixels)))
            self.begin=None;self.pixels=None
        return self.ready.popleft()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--frames',type=int,default=100);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();c=Client();rows=[]
    try:
        for _ in range(a.frames):rows.append(c.receive()[0])
    finally:c.close()
    result=dict(records=rows,stats=dict(c.matcher.stats),state_errors=c.errors,
                host_receive_fps=(len(rows)-1)/(rows[-1]['wall']-rows[0]['wall']))
    a.out.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
