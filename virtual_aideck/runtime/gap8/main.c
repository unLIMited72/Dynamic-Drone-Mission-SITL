#include "pmsis.h"
#include "bsp/bsp.h"
#include "bsp/camera.h"
#include "bsp/camera/himax.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "timestamp.h"
#ifdef EGO_STATE_LINK
#include "ego_state/receiver.h"
#endif
#if FRAME_ASSOCIATION
#include "frame_state/association.h"
#endif
#ifndef CAMERA_SESSION_ID
#error CAMERA_SESSION_ID must identify this boot/run
#endif
#ifndef TIMESTAMP_AUDIT
#define TIMESTAMP_AUDIT 0
#endif

#ifndef BENCH_SPI_MHZ
#define BENCH_SPI_MHZ 10
#endif
#ifndef BENCH_FRAMES
#define BENCH_FRAMES 20
#endif
#ifndef BENCH_VERIFY_FNV
#define BENCH_VERIFY_FNV 0
#endif

#define WIDTH 324
#define HEIGHT 244
#define IMAGE_SIZE (WIDTH * HEIGHT)
#define CAPTURE_CHUNK (64 * 1024)
#define CPX_MAX_PAYLOAD 1020
#define ESP_READY_GPIO 18
#define GAP8_NOTIFY_GPIO 3
#define ESP_READY_PAD PI_PAD_32_A13_TIMER0_CH1
#define ESP_READY_PAD_FUNC PI_PAD_32_A13_GPIO_A18_FUNC1
#define GAP8_NOTIFY_PAD PI_PAD_15_B1_RF_PACTRL3
#define GAP8_NOTIFY_PAD_FUNC PI_PAD_15_B1_GPIO_A3_FUNC1

typedef enum {
  BUFFER_FREE = 0,
  BUFFER_CAPTURING,
  BUFFER_READY,
  BUFFER_TRANSMITTING
} buffer_state_e;

typedef struct frame_buffer_s {
  uint8_t *data;
  pi_task_t tasks[2];
  volatile int pending;
  volatile int done;
  int remaining;
  int task_index;
  uint8_t *cursor;
  buffer_state_e state;
  uint32_t capture_start_us;
  volatile uint32_t capture_end_us;
  uint64_t capture_end_tick_us;
  uint32_t sequence;
  uint32_t signature;
#if FRAME_ASSOCIATION
  FrameState association;
#endif
} frame_buffer_t;

typedef struct {
  uint8_t magic;
  uint16_t width;
  uint16_t height;
  uint8_t depth;
  uint8_t type;
  uint32_t size;
} __attribute__((packed)) ImageHeader_t;

PI_L2 static frame_buffer_t frames[2];
PI_L2 static uint8_t spi_tx[CPX_MAX_PAYLOAD + 4];
static struct pi_device camera;
static struct pi_device gpio;
static struct pi_device spi;

static uint32_t stat_capture_us;
static uint32_t stat_fnv_us;
static uint32_t stat_build_us;
static uint32_t stat_handshake_us;
static uint32_t stat_spi_header_us;
static uint32_t stat_spi_payload_us;
static uint32_t stat_tx_us;
static uint32_t stat_buffer_wait_us;
static uint32_t stat_overlap_frames;
static uint32_t stat_transactions;
static capture_clock_t capture_clock;
static uint32_t timestamp_calls;
static volatile int timestamp_error;

static uint32_t image_signature(const uint8_t *data) {
  uint32_t hash=2166136261U;
  for (unsigned row=0; row<HEIGHT; ++row) {
    hash=(hash ^ data[row*WIDTH])*16777619U;
  }
  return hash;
}

static void enqueue_capture(frame_buffer_t *frame);

static void capture_complete(void *arg) {
  frame_buffer_t *frame = (frame_buffer_t *)arg;
  frame->pending--;
  enqueue_capture(frame);
  if (frame->remaining == 0 && frame->pending == 0) {
    /* Final DMA callback only: take the actual GAP8 timer sample first. */
    const uint32_t raw=(uint32_t)pi_time_get_us();
    frame->capture_end_us=raw;
    ++timestamp_calls;
    if (capture_clock_update(&capture_clock,raw,&frame->capture_end_tick_us))
      timestamp_error=1;
#if FRAME_ASSOCIATION
    frame_state_latch(&frame->association,CAMERA_SESSION_ID,frame->sequence,
                      frame->capture_end_tick_us);
#endif
    frame->signature=image_signature(frame->data);
    frame->state = BUFFER_READY;
    __asm__ volatile ("" ::: "memory");
    frame->done = 1;
  }
}

static void enqueue_capture(frame_buffer_t *frame) {
  while (frame->remaining > 0 && frame->pending < 2) {
    int size = frame->remaining < CAPTURE_CHUNK ? frame->remaining : CAPTURE_CHUNK;
    pi_task_t *task = &frame->tasks[frame->task_index];
    pi_camera_capture_async(&camera, frame->cursor, size,
                            pi_task_callback(task, capture_complete, frame));
    frame->remaining -= size;
    frame->pending++;
    frame->cursor += size;
    frame->task_index ^= 1;
  }
}

static int start_capture(frame_buffer_t *frame, uint32_t sequence) {
  if (frame->state != BUFFER_FREE) return -1;
  frame->sequence=sequence;
  frame->remaining = IMAGE_SIZE;
  frame->pending = 0;
  frame->done = 0;
  frame->task_index = 0;
  frame->cursor = frame->data;
  frame->capture_start_us = pi_time_get_us();
  frame->capture_end_us = 0;
  frame->state = BUFFER_CAPTURING;
  enqueue_capture(frame);
  return 0;
}

static void wait_capture(frame_buffer_t *frame) {
  uint32_t start = pi_time_get_us();
  while (!frame->done) {
    if ((uint32_t)(pi_time_get_us()-start)>2000000U) pmsis_exit(-20);
    pi_yield();
  }
  if(timestamp_error) pmsis_exit(-21);
  stat_buffer_wait_us += pi_time_get_us() - start;
  stat_capture_us += frame->capture_end_us - frame->capture_start_us;
}

static uint32_t fnv1a32(const uint8_t *data, uint32_t size) {
  uint32_t hash = 2166136261U;
  for (uint32_t i = 0; i < size; ++i) {
    hash ^= data[i];
    hash *= 16777619U;
  }
  return hash;
}

static int wait_ready(uint32_t expected) {
  uint32_t value = 0;
  for (unsigned attempt = 0; attempt < 20000; ++attempt) {
    if (pi_gpio_pin_read(&gpio, ESP_READY_GPIO, &value) != 0) return -1;
    if (value == expected) return 0;
    pi_time_wait_us(10);
  }
  return -1;
}

static int send_packet(const uint8_t *payload, uint16_t payload_size,
                       int direct_payload) {
  uint16_t wire_length;
  uint32_t remainder;
  uint32_t now;

  if (payload_size > CPX_MAX_PAYLOAD) return -1;
  wire_length = payload_size + 2;
  remainder = (payload_size + 3U) & ~3U;
  if (remainder < 4U) remainder = 4U;

  now = pi_time_get_us();
  memset(spi_tx, 0, direct_payload ? 4 : 4 + remainder);
  spi_tx[0] = wire_length & 0xff;
  spi_tx[1] = wire_length >> 8;
  spi_tx[2] = 0x63;
  spi_tx[3] = 0x05;
  if (!direct_payload) memcpy(spi_tx + 4, payload, payload_size);
  stat_build_us += pi_time_get_us() - now;

  now = pi_time_get_us();
  pi_gpio_pin_write(&gpio, GAP8_NOTIFY_GPIO, 1);
  if (wait_ready(1) != 0) return -2;
  stat_handshake_us += pi_time_get_us() - now;

  now = pi_time_get_us();
  pi_spi_send(&spi, spi_tx, 4 * 8, PI_SPI_LINES_SINGLE | PI_SPI_CS_KEEP);
  stat_spi_header_us += pi_time_get_us() - now;
  pi_gpio_pin_write(&gpio, GAP8_NOTIFY_GPIO, 0);

  now = pi_time_get_us();
  pi_spi_send(&spi, direct_payload ? (void *)payload : spi_tx + 4,
              remainder * 8, PI_SPI_LINES_SINGLE | PI_SPI_CS_AUTO);
  stat_spi_payload_us += pi_time_get_us() - now;
  if (wait_ready(0) != 0) return -3;
  stat_transactions++;
  return 0;
}

static int send_frame(frame_buffer_t *frame, uint32_t sequence) {
  CameraTimestampMetadata metadata;
  ImageHeader_t header;
  uint32_t offset = 0;
  uint32_t started = pi_time_get_us();

  if (frame->state != BUFFER_READY || frame->sequence != sequence) return -4;
  memset(&metadata,0,sizeof(metadata));
  metadata.magic=0xbd;
  metadata.version=2;
  metadata.kind=1;
  metadata.timestamp_source=1;
  metadata.event_type=1;
  metadata.encoding=1;
  metadata.flags=0; /* Live source, not synthetic replay. */
  metadata.session_id=CAMERA_SESSION_ID;
  metadata.sequence=frame->sequence;
  metadata.raw_tick_us=frame->capture_end_us;
  metadata.capture_end_tick_us=frame->capture_end_tick_us;
  metadata.width=WIDTH;
  metadata.height=HEIGHT;
  metadata.image_size=IMAGE_SIZE;
  metadata.image_signature=frame->signature;
  header.magic = 0xbc;
  header.width = WIDTH;
  header.height = HEIGHT;
  header.depth = 1;
  header.type = 0;
  header.size = IMAGE_SIZE;

  frame->state = BUFFER_TRANSMITTING;
  if (send_packet((uint8_t *)&metadata, sizeof(metadata), 0) != 0) return -1;
  if (send_packet((uint8_t *)&header, sizeof(header), 0) != 0) return -2;
  while (offset < IMAGE_SIZE) {
    uint16_t size = IMAGE_SIZE - offset < CPX_MAX_PAYLOAD
                        ? IMAGE_SIZE - offset
                        : CPX_MAX_PAYLOAD;
    if (send_packet(frame->data + offset, size, 1) != 0) return -3;
    offset += size;
  }
  metadata.kind=2;
  if(send_packet((uint8_t *)&metadata,sizeof(metadata),0)!=0) return -5;
#if FRAME_STATE_SEND
  uint8_t state_message[FRAME_STATE_SIZE];
  frame_state_encode(&frame->association,state_message);
  if(send_packet(state_message,sizeof(state_message),0)!=0) return -7;
#endif
#if TIMESTAMP_AUDIT
  printf("TIMESTAMP_FRAME sequence=%u raw=%u high=%u low=%u signature=%08x\n",
    frame->sequence,frame->capture_end_us,(uint32_t)(frame->capture_end_tick_us>>32),
    (uint32_t)frame->capture_end_tick_us,frame->signature);
#endif
  stat_tx_us += pi_time_get_us() - started;
  frame->state = BUFFER_FREE;
  return 0;
}

static uint32_t effective_spi_hz(uint32_t requested, uint32_t periph) {
  uint32_t div;
  if (requested >= periph) return periph / 2;
  div = (periph + requested - 1) / requested;
  if (div & 1U) div++;
  div >>= 1;
  return periph / (div * 2);
}

static int open_devices(void) {
  struct pi_himax_conf camera_conf;
  struct pi_gpio_conf gpio_conf;
  struct pi_spi_conf spi_conf;

  pi_himax_conf_init(&camera_conf);
  camera_conf.format = PI_CAMERA_QVGA;
  pi_open_from_conf(&camera, &camera_conf);
  if (pi_camera_open(&camera) != 0) return -1;

  pi_gpio_conf_init(&gpio_conf);
  pi_open_from_conf(&gpio, &gpio_conf);
  if (pi_gpio_open(&gpio) != 0) return -2;
  pi_gpio_pin_configure(&gpio, ESP_READY_GPIO, PI_GPIO_INPUT);
  pi_gpio_pin_configure(&gpio, GAP8_NOTIFY_GPIO, PI_GPIO_OUTPUT);
  pi_pad_set_function(ESP_READY_PAD, ESP_READY_PAD_FUNC);
  pi_pad_set_function(GAP8_NOTIFY_PAD, GAP8_NOTIFY_PAD_FUNC);
  pi_gpio_pin_write(&gpio, GAP8_NOTIFY_GPIO, 0);

  pi_spi_conf_init(&spi_conf);
  spi_conf.wordsize = PI_SPI_WORDSIZE_8;
  spi_conf.big_endian = 1;
  spi_conf.max_baudrate = BENCH_SPI_MHZ * 1000000;
  spi_conf.polarity = 0;
  spi_conf.phase = 0;
  spi_conf.itf = 1;
  spi_conf.cs = 0;
  pi_open_from_conf(&spi, &spi_conf);
  return pi_spi_open(&spi) == 0 ? 0 : -3;
}

static int run_runtime(void) {
  uint32_t run_start;
  uint32_t run_end;
  uint32_t periph;

  if(capture_clock_selftest()!=0) return -22;
  printf("TIMESTAMP_WRAP_SELFTEST = PASS (synthetic boundary vectors on GAP8)\n");
  uint64_t boot_tick;
  if(capture_clock_update(&capture_clock,(uint32_t)pi_time_get_us(),&boot_tick)) return -23;
  for (int i = 0; i < 2; ++i) {
    frames[i].data = pmsis_l2_malloc(IMAGE_SIZE);
    frames[i].state = BUFFER_FREE;
    if (frames[i].data == NULL) return -2;
  }
  if (open_devices() != 0) return -3;
#ifdef EGO_STATE_LINK
  if(ego_state_receiver_init() || ego_state_receiver_start()) return -30;
#endif
  periph = pi_freq_get(PI_FREQ_DOMAIN_PERIPH);
  printf("RUNTIME_CONFIG unlimited_frames=1 spi_requested_hz=%u periph_hz=%u spi_effective_hz=%u l2_frame_bytes=%u\n",
         BENCH_SPI_MHZ * 1000000U, periph,
         effective_spi_hz(BENCH_SPI_MHZ * 1000000U, periph), 2U * IMAGE_SIZE);

  run_start = pi_time_get_us();
  if(start_capture(&frames[0],0)) return -24;
  pi_camera_control(&camera, PI_CAMERA_CMD_START, 0);
  wait_capture(&frames[0]);

  for (uint32_t sequence = 0; ; ++sequence) {
    frame_buffer_t *current = &frames[sequence & 1U];
    frame_buffer_t *next = &frames[(sequence + 1U) & 1U];
    uint32_t tx_start;
    uint32_t tx_end;

    if (current->state != BUFFER_READY) return -4;
#if BENCH_VERIFY_FNV
    {
      uint32_t started = pi_time_get_us();
      uint32_t hash = fnv1a32(current->data, IMAGE_SIZE);
      stat_fnv_us += pi_time_get_us() - started;
      printf("BENCH_FRAME_FNV sequence=%u hash=0x%08x\n", sequence, hash);
    }
#endif
    if (start_capture(next, sequence+1U) != 0) return -5;
    tx_start = pi_time_get_us();
    if (send_frame(current, sequence) != 0) return -6;
    tx_end = pi_time_get_us();
    {
      wait_capture(next);
      if (next->capture_end_us >= tx_start && next->capture_end_us <= tx_end)
        stat_overlap_frames++;
    }
    if ((sequence % 100U)==0) printf("RUNTIME_FRAME sequence=%u tick_low=%u\n",sequence,current->capture_end_us);
    #ifdef EGO_STATE_LINK
    ego_state_receiver_poll();
#endif
    /* Reboot before SDK reference-clock/session limit; supervisor creates a new nonce. */
    if(capture_clock.us>=RUNTIME_SESSION_US) { printf("RUNTIME_SESSION_ROTATE\n"); return 0; }
  }

}

static void entry(void *arg) {
  (void)arg;
  pmsis_exit(run_runtime());
}

int main(void) { return pmsis_kickoff(entry); }
