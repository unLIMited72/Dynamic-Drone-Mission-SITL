# Opt-in STM32 SITL → GAP8 UART state link

Integrated runtime.json enables the qualified link and frame association; baseline.json disables it. No CRTP state proxy or clock mapping. Camera Timestamp v2 and pixels are unchanged; state uses a separate CPX envelope.

## Path and ownership

KalmanTask after externalize → coherent body state + protected latest sensor pair →
one-slot FreeRTOS overwrite mailbox → priority1 sender → nonblocking Unix datagram carrier →
native GVSoC event-based UART transmitter → GAP8 padframe UART0 → uDMA UART v1 RX →
GAP8 RISC-V framing/schema/CRC parser → latest state API.

The carrier/model never constructs state, decodes the snapshot, or accesses GAP8 memory.
The model sends every 8N1 bit through `vp::uart_slave::sync`, including repeated bit values,
as required by this SDK's bit-delivery model. This is not an analog UART oversampling or
baud-error tolerance test. The peripheral v1 consumes supplied bits and does not independently
validate baud error. Runtime uses a private module search tree; installed SDK is unchanged.

Crazyflie UART1 means USART3 PC10(TX)/PC11(RX). GAP8 side is **UART0**, RX pad38/B6,
TX pad39/A7, function0. GPIO3/18 and SPI1/CS0/CPI remain unchanged. This profile tests
STM32 UART output behavior via its SITL adapter, not STM32 USART silicon registers.

## Snapshot and scheduling

`common/snapshot.{h,c}` is a preserved copy of the earlier PoC. Schema v1 remains136 bytes,
LE float32, Body FLU velocity m/s, pqr rad/s, q xyzw B→Local World, EKF z m,
body−Z ToF m, specific force m/s². Source tick is SITL_FREERTOS_TICK (domain3), acquisition
start time, not original sample time. Original boot/sequence/tick/flags are preserved.
Sender never renumbers snapshots. Generation uses elapsed tick>=10ms, without catch-up.
The earlier camera P99=12ms strict scheduling failure remains unchanged in its report.

Producer never waits for transport. Priority1 sender is below Kalman2/sensor4/stabilizer5.
Queue capacity1; pending old value is overwritten and counted. Failed nonblocking send
is counted and dropped without retry. Kernel datagram queue is also bounded (system default datagram backlog, not a latest-overwrite queue).
A bounded number of older in-flight messages can remain there; receive freshness alone cannot prove
source freshness before clock alignment. Startup endpoint
absence and shutdown in-flight frames must not be confused with steady-state corruption.
Optional sender mmap trace stores first20,000 produced/transmitted payloads; producer itself
continues indefinitely after trace capacity. Stats continue, but trace comparison must stop
at capacity. Trace I/O/mmap is validation instrumentation and disabled unless configured.

## Wire

Application payload136 bytes, unchanged.
Raw transport record143 bytes: version u8=1, length u16 LE=136, payload136, CRC32 LE4.
CRC32 is reflected IEEE polynomial0xEDB88320, init/final xor0xFFFFFFFF over header+payload139.
COBS encoded144 bytes + delimiter0 +15 zero idle padding = **160 wire bytes**.
Zero padding also aligns160-byte DMA blocks. Decoder uses byte boundaries from delimiters,
not DMA framing. Overflow discards through next delimiter; malformed length/version/schema,
CRC, non-finite required values, bad quaternion norm, backward sequence/tick/reset generation
and duplicate packets never publish partial state.

Baud1,000,000,8N1. 1600 bit=1.6ms active per frame. A250µs inter-burst guard after each32
bytes adds1.25ms including inter-frame guard, total2.85ms GVSoC time, capacity≈350.88frames/s
in that clock. At100Hz,160kbit/s active payload+framing. Host-time capacity depends on simulator
speed; no equality of GVSoC and SITL seconds is assumed. Other baud rates are unqualified.
SDK UART driver rearms software-queued RX DMA in IRQ; guard and8×160-byte RX buffers avoid
losses seen with initial32-byte/two-buffer design. Real hardware needs this budget revalidated.

## GAP8 API and validity

`ego_state_receiver_init/start`, `ego_state_get_latest`, `ego_state_get_stats`,
`ego_state_receiver_poll` are in `runtime/gap8/ego_state/`. APIs are for the GAP8 FC context;
cluster/multicore callers need a separate synchronization contract. UART callbacks run via
PULP-OS event scheduler; getters briefly disable IRQ around coherent copies.
Camera main calls the separate frame_state latch in the final DMA callback, then sends a separate state envelope after the original image. Receiver maintenance/optional diagnostic drain remains bounded. Up to8 DMA requests and optional64-record diagnostic queue
are bounded. Diagnostics defaultOFF; when enabled, emit at most16 records per poll, outside RX callback.

Latest is updated on valid wire/schema even when source state_valid=false, and getter returns
valid=false in that case. Corrupt frames leave previous state intact; local age>250,000µs makes
getter invalid. ToF validity is independent. Receive timestamp means native parser acceptance,
which can follow DMA completion/cooperative scheduling; it is not exposure or STM32 sample time.
Raw32 GAP8 timer is extended with unsigned deltas; requires observation at least once per wrap.
Runtime session rotation and receiver boot reset are still independent of STM32 boot identity.
No subtraction of GAP8 and STM32 timestamps is performed.

First sender boot is adopted. A new boot retires the previous ID and atomically replaces state;
up to4 retired boots are rejected as replay. After4 transitions a fifth is rejected fail-closed
until receiver reinitialization/session restart. This is bounded context tracking, not authentication.
Same-boot duplicates/backward sequence/tick/reset are rejected; forward gaps counted. There is no transport retry/ACK. On owned GVSoC session rotation the supervisor removes its stale
socket endpoint before replacement; source sender retains its path and resumes after temporary errors.
Receiver starts a new context. Full multi-hour rotation is not qualified by short tests.

## Enable

The runtime-owned `build_firmware.py` builds a private firmware overlay; never replace the original cf2 binary. Integrated default startup builds the overlay automatically when absent.
Use the existing launcher `--config` with a separate state/log directory and this optional block:

```json
{"state_link":{"enabled":true,"transport":"uart","baud_rate":1000000,
 "frame_association":true,"frame_state_send":true,
 "diagnostics":false}}
```

All existing required runtime config keys remain required. `enabled` absent/false disables link;
launcher clears inherited EGO_* variables to prevent accidental enablement. The run.sh interface is unchanged. The qualified integrated default explicitly enables the link; baseline.json retains OFF. Validation runner creates separate exports, ports and evidence.
`validation_faults`, `sender_delay_ms`, sender/edge traces are explicit validation-only settings;
never enable faults for normal operation. Faults do not issue flight/control/reset commands.

Hardware sender needs a UART DMA implementation in place of the POSIX carrier, bounded completion
ownership, real tick rollover/boot ID handling and driver timing tests. Current module is SITL-native.
