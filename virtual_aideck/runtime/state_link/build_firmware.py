"""Build a private opt-in firmware overlay from production sources; no validation dependencies."""
import argparse,shutil,subprocess,difflib
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];F=R/'crazyflie-firmware';M=R/'virtual_aideck/runtime/state_link'
p=argparse.ArgumentParser();p.add_argument('destination',type=Path);a=p.parse_args();D=a.destination.resolve()
if D.exists():raise SystemExit('Refuse existing destination')
D.mkdir(parents=True)
P=D/'provenance';P.mkdir()
for n in ['src','vendor','sitl_make']:shutil.copytree(F/n,D/n,ignore=shutil.ignore_patterns('build','.git','__pycache__'))
shutil.copy2(F/'version.c',D/'version.c')
f=D/'sitl_make/CMakeLists.txt';s=f.read_text();i=s.index('#Generate version.c dependencies');j=s.index('set(CMAKE_C_FLAGS',i);s=s[:i]+'# Private validation frozen version\n'+s[j:]
s=s.replace('include(cmake/sitl_gazebo.cmake)',f'''option(EGO_STATE_LINK "Opt-in state UART sender" OFF)
if(EGO_STATE_LINK)
 target_sources(cf2 PRIVATE {M}/common/snapshot.c {M}/common/link.c {M}/stm32/producer.c)
 target_include_directories(cf2 PRIVATE {M}/common {M}/stm32)
 target_compile_definitions(cf2 PRIVATE EGO_STATE_LINK=1)
endif()''');f.write_text(s)
diff=''
def change(rel,pairs):
 global diff
 f=D/rel;old=f.read_text();s=old
 for a,b in pairs:
  assert s.count(a)==1,(rel,a);s=s.replace(a,b)
 f.write_text(s);diff+=''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile=rel,tofile=rel))
def hook(x):return '\n#ifdef EGO_STATE_LINK\n'+x+'\n#endif\n'
change('src/hal/src/sensors_sitl.c',[( '#include "sensors_sitl.h"','#include "sensors_sitl.h"'+hook('#include "producer.h"')),('processAccGyroMeasurements(&(p.data[1]));','processAccGyroMeasurements(&(p.data[1]));'+hook('egoLinkImu(&sensors.gyro,&sensors.acc,gyroBiasFound);')),('rangeSet(rangeDown, distance);','rangeSet(rangeDown, distance);'+hook('egoLinkTof(distance);'))])
change('src/modules/src/estimator/estimator_kalman.c',[( '#include "kalman_core.h"','#include "kalman_core.h"'+hook('#include "producer.h"')),('STATS_CNT_RATE_EVENT(&updateCounter);',hook('egoLinkCommit(&coreData,resetEstimation);')+'STATS_CNT_RATE_EVENT(&updateCounter);'),('void estimatorKalmanInit(void)\n{','void estimatorKalmanInit(void)\n{'+hook('egoLinkReset();'))])
(P/'firmware_overlay.patch').write_text(diff)
for mode in ['OFF','ON']:
 with (P/f'build_firmware_{mode}.log').open('x') as log:
  subprocess.run(['cmake','-S',str(D/'sitl_make'),'-B',str(D/mode),'-DEGO_STATE_LINK='+mode],stdout=log,stderr=subprocess.STDOUT,check=True)
  subprocess.run(['cmake','--build',str(D/mode),'--target','cf2','-j8'],stdout=log,stderr=subprocess.STDOUT,check=True)
