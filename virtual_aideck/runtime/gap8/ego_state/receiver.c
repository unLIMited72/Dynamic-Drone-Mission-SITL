#include "receiver.h"
#include "pmsis.h"
#include <stdio.h>
#include <string.h>
/* SDK 3.8.1 libio provides snprintf but its stdio.h omits this declaration. */
extern int snprintf(char *, size_t, const char *, ...);
static struct pi_device uart;
static LinkDecoder decoder;
static PI_L2 uint8_t buffers[8][160];
static pi_task_t tasks[8];
static uint32_t diagnostic_drops, stale_seen, invalid_seen, tof_invalid_seen;
#if EGO_STATE_DIAGNOSTICS
static uint8_t diagnostic_payload[64][136];
static uint64_t diagnostic_tick[64], diagnostic_seq[64];
static unsigned diag_in, diag_out;
#endif
static bool held[8], pause_done;
static uint64_t pause_until;
static uint32_t previous;
static uint64_t extended;
static bool clock_started;
static uint64_t now_us(void) {
  uint32_t raw = (uint32_t)pi_time_get_us();
  if (!clock_started) {
    extended = raw;
    clock_started = true;
  } else
    extended = link_extend_tick(extended, previous, raw);
  previous = raw;
  return extended;
}
static void received(void *arg) {
  unsigned i = (unsigned)(uintptr_t)arg;
  uint8_t copy[160];
  memcpy(copy, buffers[i], 160);
#if EGO_STATE_FAULTS
  if (!pause_done && decoder.stats.frames >= 450) {
    pause_done = true;
    pause_until = now_us() + 100000;
  }
#endif
  if (pause_until && now_us() < pause_until)
    held[i] = true;
  else
    pi_uart_read_async(&uart, buffers[i], 160,
                       pi_task_callback(&tasks[i], received, arg));
  if (link_feed_bytes(&decoder, copy, 160, 0)) {
      /* Timestamp acceptance once per message, not expensive timer reads per
       * byte. */
      decoder.receive_us = now_us();
#if EGO_STATE_DIAGNOSTICS
      if (diag_in - diag_out < 64) {
        unsigned k = diag_in++ % 64;
        memcpy(diagnostic_payload[k], decoder.payload, 136);
        diagnostic_tick[k] = decoder.receive_us;
        diagnostic_seq[k] = decoder.receiver_sequence;
      } else
        diagnostic_drops++;
#endif
    }
}
int ego_state_receiver_init(void) {
  memset(&decoder, 0, sizeof(decoder));
  struct pi_uart_conf c;
  pi_uart_conf_init(&c);
  c.uart_id = 0;
  c.baudrate_bps = 1000000;
  c.enable_rx = 1;
  c.enable_tx = 1;
  c.word_size = PI_UART_WORD_SIZE_8_BITS;
  c.parity_mode = PI_UART_PARITY_DISABLE;
  c.stop_bit_count = PI_UART_STOP_BITS_ONE;
  pi_pad_set_function(38, 0);
  pi_pad_set_function(39, 0);
  pi_open_from_conf(&uart, &c);
  return pi_uart_open(&uart);
}
int ego_state_receiver_start(void) {
  for (unsigned i = 0; i < 8; i++)
    if (pi_uart_read_async(
            &uart, buffers[i], 160,
            pi_task_callback(&tasks[i], received, (void *)(uintptr_t)i)))
      return -1;
  printf("EGO_UART_RX_READY uart=0 baud=1000000 8N1\n");
  return 0;
}
void ego_state_get_latest(Gap8LatestEgoState *out) {
  unsigned irq = rt_irq_disable();
  out->state = decoder.latest;
  out->gap8_receive_tick_us = decoder.receive_us;
  out->receiver_sequence = decoder.receiver_sequence;
  out->valid = link_fresh(&decoder, now_us());
  rt_irq_restore(irq);
}
void ego_state_get_stats(LinkStats *out) {
  unsigned irq = rt_irq_disable();
  *out = decoder.stats;
  rt_irq_restore(irq);
}
void ego_state_receiver_poll(void) {
  static uint64_t last;
  uint64_t now = now_us();
  if (now >= pause_until)
    for (unsigned i = 0; i < 8; i++)
      if (held[i]) {
        held[i] = false;
        pi_uart_read_async(
            &uart, buffers[i], 160,
            pi_task_callback(&tasks[i], received, (void *)(uintptr_t)i));
      }

#if EGO_STATE_DIAGNOSTICS
  for (unsigned batch = 0; batch < 16 && diag_out != diag_in; batch++) {
    unsigned k = diag_out++ % 64;
    char line[340];
    static const char hex[] = "0123456789abcdef";
    int at = snprintf(line, sizeof(line), "EGO_RX %llu %llu ",
                      (unsigned long long)diagnostic_seq[k],
                      (unsigned long long)diagnostic_tick[k]);
    for (unsigned n = 0; n < 136; n++) {
      line[at++] = hex[diagnostic_payload[k][n] >> 4];
      line[at++] = hex[diagnostic_payload[k][n] & 15];
    }
    line[at] = 0;
    printf("%s\n", line);
  }
#endif
  now = now_us();
  Gap8LatestEgoState latest;
  ego_state_get_latest(&latest);
  if (decoder.have && now - decoder.receive_us > LINK_STALE_US)
    stale_seen++;
  if (decoder.have && !(latest.state.flags & EGO_STATE_VALID))
    invalid_seen++;
  if (decoder.have && !(latest.state.flags & EGO_TOF_VALID))
    tof_invalid_seen++;
  if (now - last < 1000000)
    return;
  last = now;
  printf(
      "EGO_STATS bytes=%u frames=%u crc=%u decode=%u overflow=%u duplicate=%u "
      "gaps=%u boots=%u replay=%u valid=%u fresh=%u diag_drop=%u stale_seen=%u "
      "invalid_seen=%u tof_invalid_seen=%u age=%llu\n",
      decoder.stats.bytes, decoder.stats.frames, decoder.stats.crc_errors,
      decoder.stats.decode_errors, decoder.stats.overflow,
      decoder.stats.duplicates, decoder.stats.gaps, decoder.stats.boot_changes,
      decoder.stats.replays, decoder.stats.valid_states, latest.valid,
      diagnostic_drops, stale_seen, invalid_seen, tof_invalid_seen,
      (unsigned long long)(decoder.have ? now - decoder.receive_us : 0));
}
