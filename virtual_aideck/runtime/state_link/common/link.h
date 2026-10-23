#pragma once
#include "snapshot.h"
#define LINK_WIRE_SIZE 160
#define LINK_RAW_SIZE 143
#define LINK_STALE_US 250000u
typedef struct {
  uint32_t bytes, frames, crc_errors, decode_errors, overflow, duplicates, gaps,
      boot_changes, replays, valid_states;
} LinkStats;
typedef struct {
  uint8_t encoded[160];
  unsigned used;
  bool discard, have;
  EgoSnapshot latest;
  uint8_t payload[136];
  uint64_t receive_us, receiver_sequence;
  uint64_t retired[4];
  unsigned retired_count;
  LinkStats stats;
} LinkDecoder;
uint32_t link_crc(const uint8_t *, unsigned);
void link_encode(const uint8_t payload[136], uint8_t wire[160]);
int link_feed(LinkDecoder *, uint8_t, uint64_t now);
unsigned link_feed_bytes(LinkDecoder *, const uint8_t *, unsigned, uint64_t now);
bool link_fresh(const LinkDecoder *, uint64_t now);

/* Requires at least one observation per raw32 wrap; not cross-clock alignment.
 */
static inline uint64_t link_extend_tick(uint64_t extended, uint32_t previous,
                                        uint32_t current) {
  return extended + (uint32_t)(current - previous);
}
