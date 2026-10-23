"""Kinematic Rover with MuJoCo moving-surface contact velocities.

The prescribed Rover is externally powered and does not react to the drone.
Only the drone's contact/friction response is dynamic; no drone state, force
or constraint is written here. This is not a wheel-driven vehicle model.
"""
import math
import numpy as np
from .config import vehicle_config
from .motion.vehicle import Vehicle

class Straight:
    def __init__(self, config):
        self.speed=config['speed_mps']; self.delay=config['startup_delay_s']
    def sample(self, time):
        elapsed=max(0.,float(time)-self.delay)
        return dict(position=np.array([self.speed*elapsed,0.,0.]),yaw=0.,
                    speed=self.speed if time>=self.delay else 0.,
                    velocity=np.array([self.speed if time>=self.delay else 0.,0.,0.]),yaw_rate=0.,
                    front_angles=[0.,0.],wheel_angles=np.full(4,self.speed*elapsed/.075))

class RoverAdapter:
    def __init__(self, model, config):
        self.motion=Straight(config['rover']) if config['scenario']=='mission3_straight' else Vehicle(vehicle_config(config))
        self.mocap=int(model.body('mission3_vehicle').mocapid[0])
        if self.mocap<0: raise ValueError('rover must be mocap')
        names=[f'wheel_{s}_joint' for s in ('fl','fr','rl','rr')]+[f'steer_{s}_joint' for s in ('fl','fr')]
        self.q=[int(model.joint(n).qposadr[0]) for n in names]
        self.v=[int(model.joint(n).dofadr[0]) for n in names]
        # Contacting root geoms (pad/chassis/upper/brackets/board). Wheel-road
        # dynamics remain the original prescribed animation, not a tire model.
        import mujoco
        root = model.body('mission3_vehicle').id
        self.surface = np.flatnonzero((model.geom_bodyid == root) &
                                     ((model.geom_contype != 0) | (model.geom_conaffinity != 0)))
        self.offsets = model.geom_pos[self.surface].copy()
        transforms = []
        for geom in self.surface:
            matrix = np.empty(9)
            mujoco.mju_quat2Mat(matrix, model.geom_quat[geom])
            transforms.append(matrix.reshape(3, 3).T)
        self.to_geom = np.asarray(transforms)
        # MuJoCo 3.16 caches this at compile time. Our initially stationary
        # surface becomes nonzero at runtime; enable its supported contact path.
        model.flg_surfacevel = True
    def update(self, model, data):
        state=self.motion.sample(data.time)
        data.mocap_pos[self.mocap]=state['position']
        yaw=state['yaw']; data.mocap_quat[self.mocap]=[math.cos(yaw/2),0,0,math.sin(yaw/2)]
        data.qpos[self.q]=list(state['wheel_angles'])+list(state['front_angles'])
        data.qvel[self.v]=0.; data.qacc_warmstart[self.v]=0.
        # surfacevel is in each geom's local frame, not world/body frame.
        # Include omega x offset so every contact point sees the rigid target
        # velocity. These geoms have no dynamic-body velocity to double-count.
        co, si = math.cos(yaw), math.sin(yaw)
        vx, vy, vz = state['velocity']
        local = np.array([co*vx+si*vy, -si*vx+co*vy, vz])
        omega = state['yaw_rate']
        linear = np.broadcast_to(local, self.offsets.shape).copy()
        linear[:, 0] -= omega*self.offsets[:, 1]
        linear[:, 1] += omega*self.offsets[:, 0]
        model.geom_surfacevel[self.surface, :3] = np.einsum('nij,nj->ni', self.to_geom, linear)
        model.geom_surfacevel[self.surface, 3:] = self.to_geom[:, :, 2]*omega
        return state

def initialize(model, data, config):
    """Apply one exact world free-joint pose before agents/sockets start."""
    import mujoco
    body=model.body('cf0_drone'); joint=int(body.jntadr[0]); adr=int(model.jnt_qposadr[joint])
    yaw=config['spawn_yaw_rad']
    pose=[*config['spawn_xyz'],math.cos(yaw/2),0,0,math.sin(yaw/2)]
    model.qpos0[adr:adr+7]=pose
    data.qpos[adr:adr+7]=pose
    adapter=None
    if config['scenario'] not in ('mission1','mission2'):
        adapter=RoverAdapter(model,config); adapter.update(model,data)
    mujoco.mj_forward(model,data)
    return adapter
