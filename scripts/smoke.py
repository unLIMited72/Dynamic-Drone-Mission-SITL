"""Real MuJoCo model/render/contact smoke, not native firmware E2E."""
import sys,json,math,time
from pathlib import Path
import numpy as np,mujoco
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'virtual_aideck/runtime'))
from arena.config import resolve,SCENARIOS,vehicle_config
from arena.model_builder import build
from arena.rover_adapter import initialize
from arena.motion.vehicle import Vehicle
SIM=R/'crazyflie-firmware/tools/crazyflie-simulation/simulator_files/mujoco';sys.path.insert(0,str(SIM));import crazysim as c
OUT=R/'.local/verification';OUT.mkdir(parents=True,exist_ok=True)
results={}
for name in ('basic',*SCENARIOS):
 cfg=None if name=='basic' else resolve({'scenario':name})
 scene=None if cfg is None else str(build(cfg,R/'cache/deployment-smoke'/name))
 m=c._build_spec_multi(str(SIM/c.MODEL_PATHS[c.DEFAULT_MODEL_TYPE]),[(0,0)],c.MOTOR_PARAMS[c.DEFAULT_MODEL_TYPE],scene).compile();d=mujoco.MjData(m)
 a=initialize(m,d,cfg) if cfg else None;mujoco.mj_forward(m,d)
 with mujoco.Renderer(m,height=244,width=324) as renderer:
  renderer.update_scene(d,camera=0);im=renderer.render();assert im.shape==(244,324,3) and im.std()>0
 for _ in range(100):
  if a:a.update(m,d)
  mujoco.mj_step(m,d)
 assert np.isfinite(d.qpos).all() and not any(d.warning.number)
 result=dict(model='PASS',renderer='PASS',geoms=m.ngeom)
 if a:
  # Isolated zero-thrust fixture, not runtime landing or a flight command.
  d=mujoco.MjData(m);a=initialize(m,d,cfg);rb=m.body('mission3_vehicle').id;db=m.body('cf0_drone').id
  q=int(m.jnt_qposadr[m.body(db).jntadr[0]]);v=int(m.jnt_dofadr[m.body(db).jntadr[0]])
  d.qpos[q:q+3]=d.xpos[rb]+d.xmat[rb].reshape(3,3)@[-.05,0,.325];d.qpos[q+3:q+7]=d.xquat[rb];mujoco.mj_forward(m,d)
  for _ in range(3000):
   old=d.qpos[q:q+7].copy();a.update(m,d);assert np.array_equal(old,d.qpos[q:q+7]);mujoco.mj_step(m,d);a.update(m,d);mujoco.mj_kinematics(m,d)
  rel=d.xmat[rb].reshape(3,3).T@(d.xpos[db]-d.xpos[rb]);assert np.linalg.norm(rel[:2]-[-.05,0])<.05 and rel[2]>.31
  result['passive_contact_smoke']='PASS';result['relative_position']=rel.tolist()
 results[name]=result
for name in ('integrated','mission3'):
 for mode,route in [('loop',0),('grid',0),('grid',1),('shuttle_reverse',0),('shuttle_turn',0)]:
  cfg=resolve(dict(scenario=name,rover=dict(mode=mode,grid_route=route,speed_mps=.2)));motion=Vehicle(vehicle_config(cfg))
  for t in np.linspace(0,240,241):assert np.isfinite(motion.sample(t)['position']).all()
results['rover_modes']='PASS'
(OUT/'smoke.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
