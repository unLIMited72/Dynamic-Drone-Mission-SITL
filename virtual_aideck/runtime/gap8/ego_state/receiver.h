#pragma once
#include "link.h"
typedef struct {
  EgoSnapshot state;
  uint64_t gap8_receive_tick_us, receiver_sequence;
  bool valid;
} Gap8LatestEgoState;
int ego_state_receiver_init(void);
int ego_state_receiver_start(void);
void ego_state_get_latest(Gap8LatestEgoState *);
void ego_state_get_stats(LinkStats *);
void ego_state_receiver_poll(void);
