/* Native GVSoC timed bit transmitter. No decoder, state synthesis or GAP8
 * memory access. */
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <vp/itf/uart.hpp>
#include <vp/vp.hpp>
class StateUart : public vp::component {
  vp::uart_slave uart;
  vp::clock_event *event;
  int fd = -1, index = 160, bit = 0;
  uint8_t data[160];
  FILE *log = nullptr;
  unsigned frames = 0;
  uint64_t bits = 0;
  bool faults = false, replay_pending = false;
  static void tx(void *, int) {
  } /* unused GAP8 TX; diagnostics use semihost console */
  static void step(void *ctx, vp::clock_event *e) {
    ((StateUart *)ctx)->run(e);
  }
  void run(vp::clock_event *e) {
    if (index == 160) {
      int n;
      if (replay_pending) {
        n = 160;
        replay_pending = false;
      } else
        n = recv(fd, data, 160, MSG_DONTWAIT);
      if (n != 160) {
        event_enqueue(e, 50000); /* idle poll1ms; bit timings unchanged */
        return;
      }
      frames++;
      index = 0;
      bit = 0;
      if (faults) {
        if (frames == 500)
          replay_pending = true;
        if (frames == 200)
          data[143] = data[143] == 1 ? 2 : data[143] ^ 1;
        if (frames == 300) {
          memmove(data + 20, data + 21, 139);
          data[159] = 0;
        }
        if (frames == 400)
          memset(data + 80, 0, 80);
      }
    }
    uart.sync(bit == 0 ? 0 : bit == 9 ? 1 : (data[index] >> (bit - 1)) & 1);
    bits++;
    unsigned delay = 50; /* 50 cycles at50MHz = 1us/bit */
    if (++bit == 10) {
      bit = 0;
      index++;
      if (index % 32 == 0)
        delay += 12500;
      if (index == 160 && log) {
        fprintf(log, "%u %llu\n", frames, (unsigned long long)bits);
        fflush(log);
      }
    }
    event_enqueue(e, delay);
  }

public:
  StateUart(js::config *c) : vp::component(c) {}
  int build() override {
    uart.set_sync_meth(&StateUart::tx);
    new_slave_port("input", &uart);
    event = event_new(&StateUart::step);
    return 0;
  }
  void start() override {
    const char *path = getenv("EGO_UART_SOCKET");
    if (!path)
      abort();
    fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK, 0);
    sockaddr_un a = {};
    a.sun_family = AF_UNIX;
    if (strlen(path) >= sizeof(a.sun_path))
      abort();
    strcpy(a.sun_path, path);
    if (bind(fd, (sockaddr *)&a, sizeof(a))) {
      perror("state uart bind");
      abort();
    }
    const char *p = getenv("EGO_UART_EDGE_LOG");
    if (p)
      log = fopen(p, "wx");
    faults = getenv("EGO_FAULTS") && atoi(getenv("EGO_FAULTS"));
    event_enqueue(event, 5000);
  }
};
extern "C" vp::component *vp_constructor(js::config *c) {
  return new StateUart(c);
}
