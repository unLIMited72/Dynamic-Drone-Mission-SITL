"""Frozen-artifact selector. Never executes a generator or reads a SOURCE workspace."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from .config import BASE, VENDOR

ROOT = BASE.parents[2]
SCENE = ROOT/'crazyflie-firmware/tools/crazyflie-simulation/simulator_files/mujoco/scene.xml'

def verify_vendor():
    for item in json.loads((BASE/'provenance.json').read_text()):
        path = (BASE/item['copied_target']).resolve()
        if not path.is_relative_to(BASE) or path.is_symlink():
            raise ValueError(f'external arena resource: {path}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['target_sha256']:
            raise ValueError(f'arena provenance mismatch: {path}')

def build(config, directory):
    verify_vendor()
    directory = Path(directory).resolve()
    if not directory.is_relative_to(ROOT):
        raise ValueError('derived production scene must be within TARGET')
    directory.mkdir(parents=True, exist_ok=True)
    original = ET.parse(VENDOR/'world.xml').getroot()
    root = ET.parse(SCENE).getroot()
    # Retain TARGET physics/compiler/statistic; environment owns its explicit defaults.
    root.set('model', 'mission_arena_'+config['scenario'])
    root.find('compiler').set('angle','radian')  # frozen environment joint limits are radians
    for tag in ('asset','worldbody','visual'):
        root.remove(root.find(tag))
    visual=copy.deepcopy(original.find('visual'))
    # Preserve baseline absolute near/far with fixed TARGET extent 2.5.
    visual.find('map').set('znear', '.01'); visual.find('map').set('zfar','50')
    root.append(visual)
    assets=copy.deepcopy(original.find('asset'))
    for e in assets:
        if 'file' in e.attrib:
            p=(VENDOR/e.get('file')).resolve()
            if not p.is_relative_to(VENDOR): raise ValueError('external asset')
            e.set('file',str(p))
    root.append(assets)
    world=ET.SubElement(root,'worldbody')
    ownership=json.loads((BASE/'ownership.json').read_text())
    scenario=config['scenario']
    groups={'integrated':{'common','mission1','mission2','mission3','gate12','gate23','rover'},
            'mission1':{'common','mission1','gate12'}, 'mission2':{'common','mission2','gate12','gate23'},
            'mission3':{'common','mission3','gate23','rover'},'mission3_straight':{'common','rover'}}[scenario]
    kept=[]; excluded=[]
    defaults=original.find('default/geom').attrib
    for source in original.find('worldbody'):
        name=source.get('name')
        if source.tag!='light' and ownership[name] not in groups:
            excluded.append(name); continue
        e=copy.deepcopy(source)
        for geom in ([e] if e.tag=='geom' else list(e.iter('geom'))):
            for key,value in defaults.items(): geom.attrib.setdefault(key,value)
        # Source wheels have inferred inertia, explicitly materialize it below; do not
        # change TARGET compiler inertiafromgeom=false (drone inertia is authoritative).
        world.append(e); kept.append(name or 'environment_light')
    if scenario=='mission3_straight':
        length=config['rover']['speed_mps']*config['rover']['duration_s']+2.65
        ET.SubElement(world,'geom',name='straight_road',type='box',pos=f'{length/2-1} 0 -0.008',
                      size=f'{length/2} 1 .01',rgba='.25 .28 .3 1',contype='0',conaffinity='0')
    # Drop unused texture/material assets from standalone scenarios, keeping selected
    # definitions byte-equivalent in content. Lighting remains SOURCE lighting.
    used={g.get('material') for g in world.iter('geom') if g.get('material')}
    textures={e.get('texture') for e in assets if e.tag=='material' and e.get('name') in used}
    for e in list(assets):
        if (e.tag=='material' and e.get('name') not in used) or (e.tag=='texture' and e.get('name') not in textures): assets.remove(e)
    # Freeze SOURCE compiled inertias on jointed rover children only.
    import mujoco
    source_model=mujoco.MjModel.from_xml_path(str(VENDOR/'world.xml'))
    for body in world.iter('body'):
        if body.find('joint') is not None and body.find('inertial') is None:
            b=source_model.body(body.get('name'))
            fmt=lambda a:' '.join(format(float(x),'.17g') for x in a)
            ET.SubElement(body,'inertial',pos=fmt(b.ipos),quat=fmt(b.iquat),mass=str(float(b.mass[0])),diaginertia=fmt(b.inertia))
    path=directory/'scene.xml'; ET.indent(root); ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    manifest=dict(config=config,selected=kept,excluded=excluded,exclusion_policy='stage ownership; preview/probe/top-level debug cameras excluded; Rover inspection cameras retained',
                  scene_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (directory/'arena_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return path
