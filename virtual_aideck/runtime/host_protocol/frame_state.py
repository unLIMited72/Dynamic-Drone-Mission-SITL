"""Bounded frame-ID association, never cross-domain interpolation."""
import math
import struct
import zlib
from collections import OrderedDict, Counter
from client import ProtocolError

SNAPSHOT = struct.Struct('<HHI5Q7I15f')
ENVELOPE = struct.Struct('<4BQ I Q Q Q Q')

def decode_state(body):
    if len(body) != 188 or body[:2] != b'\xbe\x01':
        raise ProtocolError('state envelope version/length')
    if zlib.crc32(body[:184]) != struct.unpack_from('<I', body, 184)[0]:
        raise ProtocolError('state envelope CRC')
    magic, version, available, valid, session, frame, capture, received, age, rx_seq = ENVELOPE.unpack_from(body)
    if available not in (0,1) or valid not in (0,1) or valid > available or not session:
        raise ProtocolError('state flags/session')
    result = dict(session_id=session, frame_sequence=frame,
                  gap8_capture_end_tick_us=capture, state_available=bool(available),
                  state_association_valid=bool(valid), gap8_state_receive_tick_us=received,
                  state_receive_age_at_frame_us=age, receiver_sequence=rx_seq,
                  ego_state=None, payload_hex=body[48:184].hex())
    if not available:
        if received or age or rx_seq or any(body[48:184]):
            raise ProtocolError('unavailable state contains data')
        return result
    if received > capture or age != capture-received or not rx_seq:
        raise ProtocolError('future state or invalid receive age')
    v = SNAPSHOT.unpack(body[48:184])
    if v[:3] != (1,136,3): raise ProtocolError('snapshot schema/domain')
    boot,seq,tick,imu,tof = v[3:8]
    generation,imu_seq,tof_seq,flags,imu_age,tof_age,estimator = v[8:15]
    f = v[15:]
    if not boot or not seq or estimator!=2 or flags&~63 or imu>tick or tof>tick:
        raise ProtocolError('snapshot identity/flags')
    if not all(math.isfinite(x) for x in f) or abs(sum(x*x for x in f[6:10])-1)>0.001:
        raise ProtocolError('snapshot numeric validity')
    if valid and (not flags&1 or age>50000): raise ProtocolError('false association validity')
    result['ego_state']=dict(stm32_boot_id=boot,state_sequence=seq,snapshot_tick_ms=tick,
        clock_domain_id=3,reset_generation=generation,imu_receive_tick=imu,tof_receive_tick=tof,
        imu_sequence=imu_seq,tof_sequence=tof_seq,imu_age_ms=imu_age,tof_age_ms=tof_age,
        state_valid=bool(flags&1),tof_valid=bool(flags&2),flags=flags,
        body_velocity_flu=f[:3],body_angular_rate_flu=f[3:6],quaternion_xyzw=f[6:10],
        ekf_height_m=f[10],tof_distance_m=f[11],body_specific_force_flu=f[12:15])
    return result

class Matcher:
    """Per connection, capacity8. Retires sessions; never matches on adjacency.

    A missing state is released after two newer images, or flush() on EOF.
    State-only entries evict at capacity. Duplicate/conflicting metadata never
    replaces an accepted association. Callers must create a new Matcher on reconnect.
    """
    def __init__(self, capacity=8):
        self.capacity=capacity; self.images=OrderedDict(); self.states=OrderedDict()
        self.done=OrderedDict(); self.session=None; self.retired=set(); self.stats=Counter()
    def add(self, row, pixels=None):
        key=(row['session_id'],row['frame_sequence'])
        if pixels is not None:
            if key[0] in self.retired:
                self.stats['old_session']+=1; return []
            if self.session is not None and key[0]!=self.session:
                self.retired.add(self.session)
                # Bounded retired context, fail closed after excessive transitions.
                if len(self.retired)>16: raise ProtocolError('reconnect required after 16 sessions')
                self.stats['session_changes']+=1
                self.images.clear(); self.states={k:v for k,v in self.states.items() if k[0]==key[0]}
                self.states=OrderedDict(self.states)
            self.session=key[0]
        elif key[0] in self.retired:
            self.stats['old_session']+=1; return []
        target=self.images if pixels is not None else self.states
        if key in target or key in self.done:
            self.stats['duplicate']+=1; return []
        target[key]=(row,pixels) if pixels is not None else row
        result=[]
        for k,(im,px) in list(self.images.items()):
            state=self.states.get(k)
            if state is not None:
                del self.states[k]; del self.images[k]
                if state['gap8_capture_end_tick_us']!=im['gap8_capture_end_tick_us']:
                    self.stats['mismatch']+=1; state=None
                result.append((dict(im,association=state),px)); self.done[k]=True
            elif len(self.images)>2:
                del self.images[k]; self.stats['missing_state']+=1
                result.append((dict(im,association=None),px)); self.done[k]=True
        while len(self.states)>self.capacity:
            self.states.popitem(last=False); self.stats['missing_image']+=1
        while len(self.done)>self.capacity*2: self.done.popitem(last=False)
        return result
    def flush(self):
        result=[(dict(im,association=None),px) for im,px in self.images.values()]
        self.stats['missing_state']+=len(result);self.images.clear();self.states.clear()
        return result
