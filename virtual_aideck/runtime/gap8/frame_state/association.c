#include "association.h"
#include <string.h>
static void put(uint8_t *p, uint64_t value, unsigned n) {
  for(unsigned i=0;i<n;i++) p[i]=(uint8_t)(value>>(8*i));
}
void frame_state_latch(FrameState *a, uint64_t session, uint32_t frame,
                       uint64_t capture_us) {
  memset(a,0,sizeof(*a));
  a->session=session; a->frame=frame; a->capture_us=capture_us;
  ego_state_get_latest(&a->latest);
  a->available=a->latest.receiver_sequence!=0 &&
               a->latest.gap8_receive_tick_us<=capture_us;
  if(a->available) a->age_us=capture_us-a->latest.gap8_receive_tick_us;
  a->valid=a->available && a->latest.valid &&
           a->age_us<=FRAME_STATE_MAX_AGE_US;
}
void frame_state_encode(const FrameState *a, uint8_t out[FRAME_STATE_SIZE]) {
  memset(out,0,FRAME_STATE_SIZE);
  out[0]=0xbe; out[1]=1; /* independent envelope version, CPX APP */
  out[2]=a->available; out[3]=a->valid;
  put(out+4,a->session,8); put(out+12,a->frame,4);
  put(out+16,a->capture_us,8);
  if(a->available) {
    put(out+24,a->latest.gap8_receive_tick_us,8);
    put(out+32,a->age_us,8);
    put(out+40,a->latest.receiver_sequence,8);
    egoEncode(&a->latest.state,out+48);
  }
  put(out+184,link_crc(out,184),4);
}
