"""Single-client CPX APP image/timestamp v2 reader. No simulator imports."""
import hashlib
import socket
import struct
import time

META=struct.Struct('<8BQIIQHHII')
FIELDS=('magic','version','kind','timestamp_source','event_type','encoding','flags','reserved',
        'session_id','frame_sequence','raw_tick_us','gap8_capture_end_tick_us','width','height','image_size','image_signature')
class ProtocolError(Exception): pass

def exact(sock,n):
    data=bytearray()
    while len(data)<n:
        part=sock.recv(n-len(data))
        if not part: raise EOFError('Disconnected; discard partial image and reconnect at metadata begin')
        data.extend(part)
    return bytes(data)

def packet(sock):
    length=struct.unpack('<H',exact(sock,2))[0]
    if not 2<=length<=1022: raise ProtocolError('CPX bounds')
    body=exact(sock,length)
    if body[:2]!=b'\x63\x05': raise ProtocolError('CPX route/version/function/last')
    return body[2:]

def metadata(body,kind):
    if len(body)!=44: raise ProtocolError('metadata length')
    row=dict(zip(FIELDS,META.unpack(body)))
    if tuple(row[k] for k in FIELDS[:8])!=(0xbd,2,kind,1,1,1,0,0): raise ProtocolError('metadata type')
    if (row['width'],row['height'],row['image_size'])!=(324,244,79056): raise ProtocolError('geometry')
    if row['raw_tick_us']!=(row['gap8_capture_end_tick_us']&0xffffffff): raise ProtocolError('raw tick')
    return row

class Client:
    def __init__(self,host='127.0.0.1',port=5000,timeout=10):
        self.sock=socket.create_connection((host,port),timeout); self.previous=None; self.state_errors=0
    def close(self): self.sock.close()
    def receive(self):
        body=packet(self.sock)
        # Independent APP state envelopes occur between complete images.
        while body[:1]==b'\xbe':
            from frame_state import decode_state
            try: decode_state(body)
            except ProtocolError: self.state_errors+=1
            body=packet(self.sock)
        begin=metadata(body,1)
        if packet(self.sock)!=struct.pack('<BHHBBI',0xbc,324,244,1,0,79056): raise ProtocolError('image header')
        pixels=bytearray()
        while len(pixels)<79056:
            data=packet(self.sock)
            if not data or len(pixels)+len(data)>79056: raise ProtocolError('image bounds')
            pixels.extend(data)
        end=metadata(packet(self.sock),2); end['kind']=1
        if end!=begin: raise ProtocolError('image metadata association')
        signature=2166136261
        for i in range(244): signature=((signature^pixels[i*324])*16777619)&0xffffffff
        if signature!=begin['image_signature']: raise ProtocolError('GAP8 image signature')
        if self.previous:
            if begin['session_id']!=self.previous['session_id']: raise ProtocolError('session changed without reconnect')
            if begin['frame_sequence']!=self.previous['frame_sequence']+1: raise ProtocolError('sequence')
            if not 0<begin['gap8_capture_end_tick_us']-self.previous['gap8_capture_end_tick_us']<0x80000000: raise ProtocolError('timestamp')
        self.previous=begin
        return dict(begin,sha256=hashlib.sha256(pixels).hexdigest(),wall=time.monotonic()),bytes(pixels)

if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(); p.add_argument('--frames',type=int,default=20); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); client=Client(); records=[]
    try:
        for _ in range(args.frames): records.append(client.receive()[0])
    finally: client.close()
    span=records[-1]['wall']-records[0]['wall']
    result=dict(frames=len(records),receive_span_s=span,host_receive_fps=(len(records)-1)/span,records=records)
    args.out.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
