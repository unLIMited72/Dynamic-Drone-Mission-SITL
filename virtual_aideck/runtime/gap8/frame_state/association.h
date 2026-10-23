#pragma once
#include "../ego_state/receiver.h"
#define FRAME_STATE_SIZE 188
#define FRAME_STATE_MAX_AGE_US 50000u
/* One association owned by each camera buffer; no transport in DMA callback. */
typedef struct {
  Gap8LatestEgoState latest;
  uint64_t session, capture_us, age_us;
  uint32_t frame;
  bool available, valid;
} FrameState;
void frame_state_latch(FrameState *, uint64_t session, uint32_t frame,
                       uint64_t capture_us);
void frame_state_encode(const FrameState *, uint8_t out[FRAME_STATE_SIZE]);
