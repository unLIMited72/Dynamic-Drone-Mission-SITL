#ifndef EGO_SNAPSHOT_H
#define EGO_SNAPSHOT_H
#include <stdint.h>
#include <stdbool.h>
#define EGO_WIRE_SIZE 136
#define EGO_DOMAIN_SITL_TICK 3
#define EGO_STATE_VALID 1u
#define EGO_TOF_VALID 2u
#define EGO_CALIBRATED 4u
#define EGO_IMU_PRESENT 8u
#define EGO_TOF_AMBIGUOUS 16u
#define EGO_RESET_PENDING 32u
/* All times are receive/commit times, NEVER original sample times. */
typedef struct {
  uint64_t boot_id, sequence, tick_ms, imu_receive_ms, tof_receive_ms;
  uint32_t reset_generation, imu_sequence, tof_sequence, flags;
  uint32_t imu_age_ms, tof_age_ms, estimator_type;
  float velocity_b[3], angular_rate_b[3], quaternion[4];
  float ekf_height_m, tof_distance_m, specific_force_b[3];
} EgoSnapshot;
typedef struct {
  float gyro_deg[3], acc_g[3], tof_m;
  uint64_t imu_tick, tof_tick;
  uint32_t imu_sequence, tof_sequence;
  bool calibrated;
} EgoSensors;
bool egoBuild(EgoSnapshot *out, const float vb[3], const float q_wxyz[4],
              float z, const EgoSensors *s, uint64_t now, uint64_t boot,
              uint64_t seq, uint32_t generation, bool pending_reset);
void egoEncode(const EgoSnapshot *s, uint8_t out[EGO_WIRE_SIZE]);
bool egoDecode(const uint8_t *in, unsigned len, EgoSnapshot *out);
void egoRotation(const float xyzw[4], float R[3][3]);
uint32_t egoHash(const uint8_t *p, unsigned n);
#endif
