"""Startup-only arena contract; absence of arena retains the legacy scene."""
import copy
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parent
VENDOR = BASE / 'vendor/sim_final'
SCENARIOS = ('integrated', 'mission1', 'mission2', 'mission3', 'mission3_straight')
MODES = ('loop', 'grid', 'shuttle_reverse', 'shuttle_turn')

def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite in [{low}, {high}]')
    return float(value)

def resolve(raw):
    if not isinstance(raw, dict) or set(raw) - {'scenario', 'rover'}:
        raise ValueError('arena accepts scenario and rover only')
    scenario = raw.get('scenario')
    if scenario not in SCENARIOS:
        raise ValueError(f'arena.scenario must be one of {SCENARIOS}')
    rover = copy.deepcopy(raw.get('rover', {}))
    if not isinstance(rover, dict):
        raise ValueError('rover must be an object')
    if scenario in ('mission1', 'mission2') and rover:
        raise ValueError('this scenario has no rover')
    straight = scenario == 'mission3_straight'
    allowed = {'speed_mps', 'startup_delay_s', 'duration_s'} if straight else {'mode', 'speed_mps', 'grid_route', 'max_acceleration_mps2', 'initial_route_s_m', 'shuttle_behavior'}
    if set(rover) - allowed:
        raise ValueError(f'unsupported rover fields: {set(rover)-allowed}')
    spawn = {'integrated': [8.2,-1.4,.1,math.pi/2], 'mission1': [8.2,-1.4,.1,math.pi/2],
             'mission2': [7.,-1.4,.1,math.pi], 'mission3': [-17.,-1.4,.1,math.pi],
             'mission3_straight': [-1.7135,0.,.1,0.]}[scenario]
    if scenario not in ('mission1', 'mission2'):
        speed = number(rover.get('speed_mps', .15 if straight else .2), 'speed_mps', 0, .3)
        if straight:
            rover = dict(speed_mps=speed, startup_delay_s=number(rover.get('startup_delay_s',0),'startup_delay_s',0,3600),
                         duration_s=number(rover.get('duration_s',180),'duration_s',1,86400))
        else:
            if speed not in (.1,.15,.2,.3):
                raise ValueError('original Vehicle supports speed presets .10/.15/.20/.30')
            mode = rover.get('mode', 'loop')
            if mode == 'shuttle':
                behavior = rover.get('shuttle_behavior', 'reverse')
                if behavior == 'uturn': behavior = 'turn'
                if behavior not in ('reverse','turn'): raise ValueError('unknown shuttle_behavior')
                mode = 'shuttle_' + behavior
            elif 'shuttle_behavior' in rover:
                raise ValueError('shuttle_behavior is only valid with source mode shuttle')
            if mode not in MODES: raise ValueError(f'rover.mode must be one of {MODES}')
            route = rover.get('grid_route',0)
            if type(route) is not int or route not in (0,1): raise ValueError('grid_route must be 0 or 1')
            acc = number(rover.get('max_acceleration_mps2',.2),'max_acceleration_mps2',.1,.2)
            if acc not in (.1,.2): raise ValueError('acceleration presets .1/.2 only')
            rover = dict(mode=mode,speed_mps=speed,grid_route=route,max_acceleration_mps2=acc,
                         initial_route_s_m=number(rover.get('initial_route_s_m',0),'initial_route_s_m',0,1000))
    return dict(scenario=scenario,rover=rover,spawn_xyz=spawn[:3],spawn_yaw_rad=spawn[3])

def vehicle_config(config):
    c = json.loads((VENDOR/'config.json').read_text())
    r = config['rover']; mode = r['mode']
    c['vehicle'].update({k:v for k,v in r.items() if k != 'mode'})
    c['vehicle']['mode'] = 'shuttle' if mode.startswith('shuttle_') else mode
    c['vehicle']['shuttle_behavior'] = 'turn' if mode == 'shuttle_turn' else 'reverse'
    return c
