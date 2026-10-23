#ifndef CAMERA_TIMESTAMP_H
#define CAMERA_TIMESTAMP_H
#include <stdint.h>

/* Single FC callback owner. Valid if successive samples are < 2^31 us
 * apart, timer is not reset, and native reference counter has not wrapped.
 * A backward/out-of-order value or ambiguous long gap is rejected. */
typedef struct { uint64_t us; uint32_t last; int initialized; } capture_clock_t;
static int capture_clock_update(capture_clock_t *clock, uint32_t raw, uint64_t *out) {
  if (!clock->initialized) {
    clock->us=raw; clock->last=raw; clock->initialized=1;
  } else {
    uint32_t elapsed=raw-clock->last;
    if (elapsed >= 0x80000000U) return -1;
    clock->us += elapsed;
    clock->last=raw;
  }
  /* This SDK's underlying 32768-Hz 32-bit reference counter also wraps.
   * Restrict each session to 24 h, below that native rollover (~36.4 h).
   * Continuous sampling <35.8 min apart is still a precondition. */
  if (clock->us >= 86400000000ULL) return -2;
  *out=clock->us;
  return 0;
}

static int capture_clock_selftest(void) {
  capture_clock_t clock={0}; uint64_t out;
  /* Volatile inputs keep this a runtime arithmetic test on GAP8 at -O3.
   * This independent state never supplies timestamps to camera frames. */
  volatile uint32_t samples[]={0xfffffff0U,0xfffffff8U,0x18U,0x18U,
                              0x17U,0x80000018U,0x38U,1U};
  if(capture_clock_update(&clock,samples[0],&out) || out!=0xfffffff0ULL) return 1;
  if(capture_clock_update(&clock,samples[1],&out) || out!=0xfffffff8ULL) return 2;
  if(capture_clock_update(&clock,samples[2],&out) || out!=0x100000018ULL) return 3;
  if(capture_clock_update(&clock,samples[3],&out) || out!=0x100000018ULL) return 4;
  if(capture_clock_update(&clock,samples[4],&out)!=-1) return 5;
  if(capture_clock_update(&clock,samples[5],&out)!=-1) return 6;
  if(capture_clock_update(&clock,samples[6],&out) || out!=0x100000038ULL) return 7;
  clock.us=86399999999ULL; clock.last=0; clock.initialized=1;
  if(capture_clock_update(&clock,samples[7],&out)!=-2) return 8;
  return 0;
}

/* Packed little-endian CPX APP payload, independent of Bitcraze image header.
 * 1=begin, 2=end. Source=1 pi_time_get_us; event=1 final DMA completion
 * callback observation; encoding=1 MONO8; flags=1 synthetic CPI source. */
typedef struct {
  uint8_t magic, version, kind, timestamp_source;
  uint8_t event_type, encoding, flags, reserved;
  uint64_t session_id;
  uint32_t sequence;
  uint32_t raw_tick_us;
  uint64_t capture_end_tick_us;
  uint16_t width, height;
  uint32_t image_size;
  uint32_t image_signature;
} __attribute__((packed)) CameraTimestampMetadata;
typedef char timestamp_size_check[sizeof(CameraTimestampMetadata)==44 ? 1 : -1];
#endif
