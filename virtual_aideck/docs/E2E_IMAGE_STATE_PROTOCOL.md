# Image + Ego-State protocol

This opt-in extension preserves the existing 324×244 MONO8 image, 44-byte Timestamp v2 begin/end messages, image header and CPX APP routing (route bytes `63 05`). A separate state envelope is sent **after** each complete image. Virtual ESP32 transparently forwards the same CPX packets over TCP5000. No second server exists.

TCP framing remains uint16 little-endian CPX length, two routing bytes, payload. Reads may split or combine packets. Pixel packets are arbitrary binary and are only interpreted in the image-transfer state; a pixel prefix is never treated as state metadata.

## State envelope v1 (188 bytes)

|Offset|Type|Meaning|
|---:|---|---|
|0|u8|magic 0xBE|
|1|u8|envelope version 1|
|2|u8|state_available (0/1)|
|3|u8|state_association_valid (0/1)|
|4|u64 LE|GAP8 camera session ID|
|12|u32 LE|camera frame sequence|
|16|u64 LE|GAP8 capture-end tick, µs|
|24|u64 LE|GAP8 state receive/validation tick, µs|
|32|u64 LE|state_receive_age_at_frame_us|
|40|u64 LE|GAP8 accepted receiver sequence|
|48|136 bytes|unchanged Ego Snapshot schema v1|
|184|u32 LE|IEEE CRC32 of preceding184 bytes|

CPX TCP wire length is192 bytes including two-byte length and routing. SPI transaction uses the same padded192 bytes. Snapshot schema version and envelope version are independent. CRC uses the same standard CRC32 implementation as the UART link; transport UART framing remains160 bytes,1Mbps8N1.

If unavailable, bytes24–183 are zero. A stale/source-invalid state may be available but association_valid=false. ToF validity is independent of overall state validity.

## Snapshot schema (unchanged)

`<HHI5Q7I15f`,136 bytes, little-endian IEEE Float32:

- version1, size136, clock-domain3 (`SITL_FREERTOS_TICK`)
- u64 boot_id, sequence, snapshot_tick_ms, imu_receive_ms, tof_receive_ms
- u32 reset_generation, imu_sequence, tof_sequence, flags, imu_age_ms, tof_age_ms, estimator_type
- float32 velocity_b[3], angular_rate_b[3], quaternion_xyzw[4], ekf_height_m, tof_distance_m, specific_force_b[3]

Flags: state_valid1, tof_valid2, calibrated4, IMU-present8, ToF-ambiguous16, reset-pending32. Velocity is Body FLU m/s; angular rate Body FLU rad/s; quaternion Body FLU→Local World XYZW; EKF height Local World +Z metres; ToF Body−Z ray metres; specific force Body FLU m/s². No gravity removal or FRD conversion. No geographic ENU promise.

## Association semantics

The final camera DMA callback samples the existing capture clock first, then copies the latest fully validated UART state into the camera buffer's own association. Each camera buffer retains that copy through SPI transmission. CRC, serialization and SPI transmission occur outside the callback.

Both GAP8 timestamps derive from the same reference timer with unsigned raw32 extension, initialized in the same boot before rollover. Receive time is parser acceptance, capture time is final DMA callback observation, not exposure. Reject future state (`receive > capture`); allow maximum receive age50,000µs for valid association. A missing or invalid state never suppresses the image. Latest source-invalid messages invalidate association rather than making old good data appear new.

`capture - receive` is exclusively GAP8 receive age. It is **not** sensor sample age, UART delay or a subtraction between clocks. STM32 snapshot_tick is commit time, not every sensor's sampling time. No clock alignment, offset/rate estimator, interpolation, SLERP or extrapolation exists.

## Host rules and compatibility

Use `runtime/host_protocol/e2e_client.py` for images plus state; `client.py` retains its image-only API and skips checked state envelopes between images. An old external binary parser that assumes every next message is image-begin must be upgraded or use the baseline OFF profile.

Matching key is `(gap8_session_id,frame_sequence)` with exact capture-tick equality. The bounded Matcher accepts image/state order variation, counts duplicates/missing data and retires old sessions. Maximum8 pending state envelopes; unmatched images are released after two newer images or explicit EOF flush. At connection reset discard all partial messages and create a new Client. ESP32 resumes a new connection only at complete image-begin metadata. No concurrent multi-client guarantee.

STM32 boot ID is separate from camera session. Receiver switches whole validated state on new boot and rejects remembered retired boots; no fields merge across boots. Each GAP8 boot resets associations. Already latched frames retain their historical boot identity, rather than rewriting state after capture. Session retirement is bounded (16 transitions, then reconnect required).

## Performance implementation

GAP8 receives the same UART/uDMA bytes. The decoder batches nonzero COBS spans to avoid per-byte FC function calls and counter stores, then invokes the unchanged delimiter/CRC/schema validator. DMA chunk size and UART bit rate remain unchanged. Native UART idle socket polling is1ms; start/data/stop bits still advance1µs each, with existing guard intervals. This bounds additional discovery delay in GVSoC time and must be evaluated with receive-age measurements.
