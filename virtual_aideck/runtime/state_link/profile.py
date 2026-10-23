"""Opt-in launcher wiring only; no state computation or decoding on Host."""
import os,secrets
from pathlib import Path
def configure(cfg,ipc_path,root):
    poll=int(cfg.get('network_poll_us',10))
    if poll not in (10,100):raise ValueError('network_poll_us must be 10 or 100')
    os.environ['RUNTIME_NETWORK_POLL_US']=str(poll)
    link=cfg.get('state_link',{})
    default=root/'crazyflie-firmware/sitl_make/build/cf2'
    if not link.get('enabled',False):
        # Ambient shell variables must not silently enable state transport.
        for key in list(os.environ):
            if key.startswith('EGO_'):os.environ.pop(key)
        return default
    if link.get('transport','uart')!='uart' or link.get('baud_rate',1000000)!=1000000:
        raise ValueError('Only validated uart/1000000 profile supported')
    for key in list(os.environ):
        if key.startswith('EGO_'):os.environ.pop(key)
    binary=Path(link.get('firmware_binary',root/'virtual_aideck/runtime/build/ego_firmware/ON/cf2'))
    if not binary.is_absolute():binary=root/binary
    binary=binary.resolve()
    if not binary.is_file() and 'firmware_binary' not in link:
        import subprocess,sys
        subprocess.run([sys.executable,str(root/'virtual_aideck/runtime/state_link/build_firmware.py'),str(binary.parents[1])],check=True)
    if not binary.is_file():raise ValueError('Opt-in firmware_binary required')
    os.environ.update(EGO_FAULTS=str(int(link.get('validation_faults',False))),EGO_STATE_LINK='1',EGO_UART_SOCKET=str(Path(ipc_path).with_name('state_uart.sock')),
                      EGO_BOOT_ID=str(secrets.randbits(64) or 1),EGO_STATE_DIAGNOSTICS=str(int(link.get('diagnostics',False))))
    if link.get('producer_only',False):
        os.environ.update(EGO_PRODUCER_ONLY='1',EGO_STATE_LINK='0')
    os.environ['EGO_FRAME_ASSOCIATION']=str(int(link.get('frame_association',False)))
    os.environ['EGO_FRAME_SEND']=str(int(link.get('frame_state_send',False)))
    if link.get('frame_state_send') and not link.get('frame_association'):
        raise ValueError('frame_state_send requires frame_association')
    for key,env in [('sender_trace','EGO_SENDER_TRACE'),('edge_log','EGO_UART_EDGE_LOG'),('sender_delay_ms','EGO_SENDER_DELAY_MS')]:
        if key in link:os.environ[env]=str(link[key])
    return binary

def prepare_gvsoc(cfg):
    """Called only after the prior owned GVSoC exited, before its replacement."""
    if not cfg.get('state_link',{}).get('enabled',False):return
    import stat
    path=Path(os.environ['EGO_UART_SOCKET'])
    if path.exists():
        if not stat.S_ISSOCK(path.lstat().st_mode):raise ValueError('Refuse non-socket UART endpoint')
        path.unlink()
