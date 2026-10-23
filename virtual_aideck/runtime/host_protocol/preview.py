"""Optional localhost browser preview. One pending frame; never blocks receiver."""
import http.server
import queue
import struct
import threading
import zlib

class Preview:
    def __init__(self,port):
        self.pending=queue.Queue(1); self.latest=b''; self.count=0
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                data=owner.latest if self.path.startswith('/frame') else b'<img id="im"><script>setInterval(()=>im.src="/frame?"+Date.now(),100)</script>'
                self.send_response(200); self.send_header('Content-Type','image/png' if self.path.startswith('/frame') else 'text/html'); self.end_headers(); self.wfile.write(data)
            def log_message(self,*args): pass
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        threading.Thread(target=self.encode,daemon=True).start()
    def offer(self,image):
        try: self.pending.get_nowait()
        except queue.Empty: pass
        self.pending.put_nowait(image)
    def encode(self):
        def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        while True:
            image=self.pending.get()
            data=b''.join(b'\0'+image[i:i+324] for i in range(0,len(image),324))
            self.latest=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',324,244,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(data,1))+chunk(b'IEND',b'')
            self.count+=1
