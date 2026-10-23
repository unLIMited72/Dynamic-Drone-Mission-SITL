#include "snapshot.h"
#include <math.h>
#include <string.h>
#include <float.h>
#include <limits.h>
_Static_assert(sizeof(float)==4 && FLT_RADIX==2 && FLT_MANT_DIG==24, "IEEE binary32 required");
static uint32_t age(uint64_t now, uint64_t then, uint32_t seq) {
  if (!seq || now<then || now-then>UINT32_MAX) return UINT32_MAX;
  return (uint32_t)(now-then);
}
bool egoBuild(EgoSnapshot *o, const float v[3], const float q[4], float z,
              const EgoSensors *s, uint64_t now, uint64_t boot,
              uint64_t seq, uint32_t gen, bool pending) {
  memset(o,0,sizeof(*o));
  o->boot_id=boot; o->sequence=seq; o->tick_ms=now; o->reset_generation=gen;
  o->estimator_type=2; o->imu_receive_ms=s->imu_tick; o->tof_receive_ms=s->tof_tick;
  o->imu_sequence=s->imu_sequence; o->tof_sequence=s->tof_sequence;
  o->imu_age_ms=age(now,s->imu_tick,s->imu_sequence);
  o->tof_age_ms=age(now,s->tof_tick,s->tof_sequence);
  o->flags=(s->calibrated?EGO_CALIBRATED:0)|(s->imu_sequence?EGO_IMU_PRESENT:0)|
           (pending?EGO_RESET_PENDING:0);
  float n=0; for(unsigned i=0;i<4;i++) n+=q[i]*q[i];
  bool good=isfinite(n) && n>0.99f && n<1.01f && isfinite(z);
  if (good) { float inv=1.0f/sqrtf(n); for(unsigned i=0;i<4;i++) o->quaternion[i]=q[(i+1)%4]*inv; }
  else o->quaternion[3]=1; /* finite fallback, state_valid remains false */
  for(unsigned i=0;i<3;i++) {
    o->velocity_b[i]=v[i]; o->angular_rate_b[i]=s->gyro_deg[i]*0.017453292519943295f;
    o->specific_force_b[i]=s->acc_g[i]*9.81f;
    good=good && isfinite(v[i]) && isfinite(o->angular_rate_b[i]) && isfinite(o->specific_force_b[i]);
  }
  o->ekf_height_m=z; o->tof_distance_m=s->tof_m;
  /* 4m is ambiguous: both real max distance and no-hit use that number.
     Conservative validity is profile-specific, NOT a hardware hit detector. */
  if (s->tof_sequence && (!isfinite(s->tof_m) || s->tof_m>=4.0f)) o->flags|=EGO_TOF_AMBIGUOUS;
  if (s->tof_sequence && isfinite(s->tof_m) && s->tof_m>0.01f && s->tof_m<4.0f && o->tof_age_ms<=100)
    o->flags|=EGO_TOF_VALID;
  if(good && boot && s->calibrated && o->imu_age_ms<=20 && !pending) o->flags|=EGO_STATE_VALID;
  return (o->flags&EGO_STATE_VALID)!=0;
}
void egoRotation(const float q[4], float R[3][3]) {
  float x=q[0],y=q[1],z=q[2],w=q[3];
  R[0][0]=w*w+x*x-y*y-z*z; R[0][1]=2*(x*y-w*z); R[0][2]=2*(x*z+w*y);
  R[1][0]=2*(x*y+w*z); R[1][1]=w*w-x*x+y*y-z*z; R[1][2]=2*(y*z-w*x);
  R[2][0]=2*(x*z-w*y); R[2][1]=2*(y*z+w*x); R[2][2]=w*w-x*x-y*y+z*z;
}
static void put(uint8_t **p,uint64_t v,unsigned n) { for(unsigned i=0;i<n;i++) *(*p)++=(uint8_t)(v>>(8*i)); }
static uint64_t get(const uint8_t **p,unsigned n) { uint64_t v=0;for(unsigned i=0;i<n;i++) v|=(uint64_t)*(*p)++<<(8*i);return v; }
static void pf(uint8_t **p,float f) { uint32_t u;memcpy(&u,&f,4);put(p,u,4); }
static float gf(const uint8_t **p) { uint32_t u=(uint32_t)get(p,4);float f;memcpy(&f,&u,4);return f; }
void egoEncode(const EgoSnapshot *s,uint8_t out[EGO_WIRE_SIZE]) {
  uint8_t *p=out;put(&p,1,2);put(&p,EGO_WIRE_SIZE,2);put(&p,EGO_DOMAIN_SITL_TICK,4);
#define U64(x) put(&p,s->x,8)
  U64(boot_id);U64(sequence);U64(tick_ms);U64(imu_receive_ms);U64(tof_receive_ms);
#undef U64
#define U32(x) put(&p,s->x,4)
  U32(reset_generation);U32(imu_sequence);U32(tof_sequence);U32(flags);U32(imu_age_ms);U32(tof_age_ms);U32(estimator_type);
#undef U32
  for(unsigned i=0;i<3;i++) pf(&p,s->velocity_b[i]);
  for(unsigned i=0;i<3;i++) pf(&p,s->angular_rate_b[i]);
  for(unsigned i=0;i<4;i++) pf(&p,s->quaternion[i]);
  pf(&p,s->ekf_height_m);pf(&p,s->tof_distance_m);
  for(unsigned i=0;i<3;i++) pf(&p,s->specific_force_b[i]);
}
bool egoDecode(const uint8_t *in,unsigned len,EgoSnapshot *s) {
  if(len!=EGO_WIRE_SIZE) return false;
  const uint8_t *p=in;
  if(get(&p,2)!=1 || get(&p,2)!=EGO_WIRE_SIZE || get(&p,4)!=EGO_DOMAIN_SITL_TICK) return false;
  memset(s,0,sizeof(*s));
#define U64(x) s->x=get(&p,8)
  U64(boot_id);U64(sequence);U64(tick_ms);U64(imu_receive_ms);U64(tof_receive_ms);
#undef U64
#define U32(x) s->x=(uint32_t)get(&p,4)
  U32(reset_generation);U32(imu_sequence);U32(tof_sequence);U32(flags);U32(imu_age_ms);U32(tof_age_ms);U32(estimator_type);
#undef U32
  for(unsigned i=0;i<3;i++) s->velocity_b[i]=gf(&p);
  for(unsigned i=0;i<3;i++) s->angular_rate_b[i]=gf(&p);
  for(unsigned i=0;i<4;i++) s->quaternion[i]=gf(&p);
  s->ekf_height_m=gf(&p);s->tof_distance_m=gf(&p);
  for(unsigned i=0;i<3;i++) s->specific_force_b[i]=gf(&p);
  return true;
}
uint32_t egoHash(const uint8_t *p,unsigned n) { uint32_t h=2166136261u;while(n--)h=(h^*p++)*16777619u;return h; }
