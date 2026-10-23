/* SITL adaptation: FreeRTOS producer/mailbox/sender; socket is virtual wire
 * carrier only. */
#include "producer.h"
#include "FreeRTOS.h"
#include "link.h"
#include "queue.h"
#include "task.h"
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#define TRACE_CAP 20000u
_Static_assert(sizeof(Axis3f) == 12, "Axis3f layout");
_Static_assert(configTICK_RATE_HZ_RAW == 1000, "1ms tick required");
static EgoSensors latest;
static QueueHandle_t mailbox;
static uint64_t seq, last, boot;
static uint32_t generation, produced, sent, drops, errors, skipped;
static bool fault, producer_only;
static uint8_t *trace;
static int sock = -1;
static struct sockaddr_un endpoint;
static void count(unsigned off, uint32_t n) {
  if (trace)
    __atomic_store_n((uint32_t *)(trace + off), n, __ATOMIC_RELEASE);
}
static void sender(void *unused) {
  (void)unused;
  uint8_t payload[136], wire[160];
  for (;;) {
    if (xQueueReceive(mailbox, payload, portMAX_DELAY) == pdTRUE) {
      const char *delay = getenv("EGO_SENDER_DELAY_MS");
      if (delay)
        vTaskDelay(atoi(delay));
      if (fault) {
        uint64_t n = 0;
        memcpy(&n, payload + 16, 8);
        if (n >= 600 && n < 750) {
          count(16, ++skipped);
          continue;
        }
      }
      if (producer_only) continue;
      link_encode(payload, wire);
      /* Nonblocking, no retransmission of old state. Next mailbox value wins.
       */
      int n = sendto(sock, wire, 160, MSG_DONTWAIT,
                     (struct sockaddr *)&endpoint, sizeof(endpoint));
      if (n == 160) {
        if (trace && sent < TRACE_CAP)
          memcpy(trace + 64 + TRACE_CAP * 136 + sent * 136, payload, 136);
        sent++;
        count(4, sent);
      } else {
        errors++;
        count(12, errors);
      }
    }
  }
}
void egoLinkReset(void) {
  ++generation;
  if (mailbox)
    return;
  const char *path = getenv("EGO_UART_SOCKET"), *id = getenv("EGO_BOOT_ID");
  if (!path || !id)
    return;
  producer_only = getenv("EGO_PRODUCER_ONLY") && atoi(getenv("EGO_PRODUCER_ONLY"));
  fault = getenv("EGO_FAULTS") && atoi(getenv("EGO_FAULTS"));
  boot = strtoull(id, 0, 0);
  if (!boot || strlen(path) >= sizeof(endpoint.sun_path))
    abort();
  sock = socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK, 0);
  if (sock < 0)
    abort();
  endpoint.sun_family = AF_UNIX;
  strcpy(endpoint.sun_path, path);
  const char *log = getenv("EGO_SENDER_TRACE");
  if (log) {
    int fd = open(log, O_RDWR | O_CREAT | O_EXCL, 0600);
    size_t size = 64 + 2 * TRACE_CAP * 136;
    if (fd < 0 || ftruncate(fd, size))
      abort();
    trace = mmap(0, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (trace == MAP_FAILED)
      abort();
  }
  mailbox = xQueueCreate(1, 136);
  if (!mailbox || xTaskCreate(sender, "ego_uart", 2048, 0, 1, 0) != pdPASS)
    abort();
}
void egoLinkImu(const Axis3f *g, const Axis3f *a, bool c) {
  if (!mailbox)
    return;
  taskENTER_CRITICAL();
  memcpy(latest.gyro_deg, g, 12);
  memcpy(latest.acc_g, a, 12);
  latest.imu_tick = xTaskGetTickCount();
  latest.imu_sequence++;
  latest.calibrated = c;
  taskEXIT_CRITICAL();
}
void egoLinkTof(float d) {
  if (!mailbox)
    return;
  taskENTER_CRITICAL();
  latest.tof_m = d;
  latest.tof_tick = xTaskGetTickCount();
  latest.tof_sequence++;
  taskEXIT_CRITICAL();
}
void egoLinkCommit(const kalmanCoreData_t *k, bool pending) {
  if (!mailbox)
    return;
  uint64_t now = xTaskGetTickCount();
  if (seq && now - last < 10)
    return;
  EgoSensors sensor;
  taskENTER_CRITICAL();
  sensor = latest;
  now = xTaskGetTickCount();
  taskEXIT_CRITICAL();
  if (fault && produced == 1200) {
    boot ^= 0x100000001ULL;
    seq = 0;
  } /* isolated logical sender-session restart fixture */
  float v[3] = {k->S[KC_STATE_PX], k->S[KC_STATE_PY], k->S[KC_STATE_PZ]};
  EgoSnapshot s;
  egoBuild(&s, v, k->q, k->S[KC_STATE_Z], &sensor, now, boot, ++seq, generation,
           pending);
  if (fault && produced >= 800 && produced < 820)
    s.flags &= ~EGO_STATE_VALID;
  if (fault && produced >= 820 && produced < 840)
    s.flags &= ~EGO_TOF_VALID;
  uint8_t data[136];
  egoEncode(&s, data);
  taskENTER_CRITICAL();
  if (uxQueueMessagesWaiting(mailbox))
    drops++;
  xQueueOverwrite(mailbox, data);
  taskEXIT_CRITICAL();
  if (trace && produced < TRACE_CAP)
    memcpy(trace + 64 + produced * 136, data, 136);
  produced++;
  count(0, produced);
  count(8, drops);
  last = now;
}
