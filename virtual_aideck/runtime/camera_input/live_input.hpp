#pragma once
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <openssl/sha.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <time.h>
#include <cerrno>
extern "C" int64_t dpi_time(void *handle, int64_t unused);

class LiveInput {
  struct __attribute__((packed)) Header { uint64_t session,seq,sim_ns; unsigned char sha[32]; };
  int listener=-1,client=-1; uint64_t last=0,session=0,latched=0,limit=0,polls=0;
  bool seen=false; unsigned pos=0; uint64_t idle_ticks=0;
  unsigned char packet[sizeof(Header)+79056],pixels[79056];
  Header current{};
  int64_t last_latch_ps=-1;
  static double wall() { timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec+t.tv_nsec*1e-9; }
 public:
  LiveInput() {
    const char *path=getenv("LIVE_CAMERA_SOCKET"), *cap=getenv("LIVE_CAMERA_LIMIT");
    if(!path || !cap || strlen(path)>=sizeof(sockaddr_un::sun_path)) throw std::runtime_error("live camera configuration");
    limit=strtoull(cap,nullptr,10);
    listener=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_NONBLOCK,0);
    sockaddr_un addr{}; addr.sun_family=AF_UNIX; strcpy(addr.sun_path,path);
    if(listener<0 || bind(listener,(sockaddr*)&addr,sizeof(addr)) || listen(listener,1)) throw std::runtime_error("live camera bind (never unlink existing socket)");
    fprintf(stderr,"LIVE_CAMERA_READY socket=%s limit=%llu\n",path,(unsigned long long)limit);
  }
  bool latch(void *handle) {
    // Initial blanking permits normal GAP8 driver boot/DMA arming, no pixel injection.
    if(++idle_ticks<400000 || (limit && latched>=limit)) return false;
    if((++polls & 4095)!=0) return false;
    const int64_t now=dpi_time(handle,0);
    // Sensor frame-rate cap: 31.25 Hz in sensor/GVSoC time. Blank CPI between
    // frames, preserving every SPI event. Never repeat an old source image.
    if(last_latch_ps>=0 && now-last_latch_ps<32000000000LL) return false;
    if(client<0) {
      client=accept4(listener,nullptr,nullptr,SOCK_NONBLOCK);
      if(client<0 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR)
        throw std::runtime_error("live camera accept error");
      return false;
    }
    bool available=false;
    for(int i=0;i<4;++i) {
      ssize_t n=recv(client,packet,sizeof(packet),MSG_DONTWAIT|MSG_TRUNC);
      if(n<0) {
        if(errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR)
          throw std::runtime_error("live camera receive error");
        break;
      }
      if(n==0) { fprintf(stderr,"LIVE_INPUT_DISCONNECTED\n"); close(client); client=-1; break; }
      if(n!=sizeof(packet)) { fprintf(stderr,"LIVE_REJECT size=%ld\n",(long)n); continue; }
      Header h; memcpy(&h,packet,sizeof(h)); unsigned char digest[32];
      SHA256(packet+sizeof(h),79056,digest);
      if(memcmp(h.sha,digest,32) || (seen && (h.session!=session || h.seq<=last))) {
        fprintf(stderr,"LIVE_REJECT identity_or_digest seq=%llu\n",(unsigned long long)h.seq); continue;
      }
      if(available) fprintf(stderr,"LIVE_LATEST_DROP seq=%llu\n",(unsigned long long)current.seq);
      current=h; memcpy(pixels,packet+sizeof(h),79056);
      last=h.seq; session=h.session; seen=true; available=true;
    }
    if(!available) return false;
    pos=0; ++latched; last_latch_ps=now;
    char hex[65]; for(int i=0;i<32;++i) sprintf(hex+i*2,"%02x",current.sha[i]);
    fprintf(stderr,"LIVE_LATCH index=%llu session=%llu seq=%llu sha256=%s wall=%.9f\n",
      (unsigned long long)(latched-1),(unsigned long long)session,(unsigned long long)last,hex,wall());
    return true;
  }
  unsigned pixel() {
    if(pos>=79056) throw std::runtime_error("live pixel bounds");
    unsigned result=pixels[pos++];
    if(pos==79056) fprintf(stderr,"LIVE_EMIT_COMPLETE index=%llu seq=%llu bytes=79056 wall=%.9f\n",
      (unsigned long long)(latched-1),(unsigned long long)last,wall());
    return result;
  }
};
