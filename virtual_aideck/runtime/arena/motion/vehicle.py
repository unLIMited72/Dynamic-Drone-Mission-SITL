"""Reference paths and independently integrated rear-axle bicycle state."""
import math
import numpy as np
from .paths import StadiumPath, RoundedGrid

class Reference:
    def __init__(self,path=None,reverse=False):
        self.closed=not reverse
        self.length=11. if reverse else path.length
        self.ds=self.length/max(2,math.ceil(self.length/.035))
        self.s=np.arange(0,self.length,self.ds)
        poses=[]
        for s in self.s:
            if reverse:xy,yaw=np.array([-5.5+s,0]),0.
            elif isinstance(path,StadiumPath):p=path.pose(s);xy,yaw=np.array([p.x,p.y]),p.yaw
            else:xy,yaw=path.pose(s)
            poses.append([*xy,yaw])
        self.poses=np.asarray(poses);self.xy=self.poses[:,:2]
    def at(self,s):
        if self.closed:s%=self.length
        else:s=np.clip(s,0,self.length-self.ds)
        i=int(s/self.ds)%len(self.xy);j=(i+1)%len(self.xy)
        u=(s/self.ds)%1
        return self.xy[i]*(1-u)+self.xy[j]*u

def paths(c):
    t=c['track']
    return {'loop':Reference(StadiumPath(4,4)), 'grid0':Reference(RoundedGrid(t['grid_routes'][0],1.4)), 'grid1':Reference(RoundedGrid(t['grid_routes'][1],1.4)), 'shuttle_reverse':Reference(reverse=True),'shuttle_uturn':Reference(StadiumPath(5.5,1.5))}

def clip(x,lo,hi):return min(hi,max(lo,x))

def ackermann(delta,L=.44,T=.47):
    k=math.tan(delta)/L
    return [math.atan2(L*k,1-y*k) for y in [T/2,-T/2]]

class Vehicle:
    # State: rear x,y,yaw,signed v,equivalent steer,unwrapped path s,
    # wheel fl/fr/rl/rr rotation,dwell remaining,direction,acceleration,steer rate,error.
    def __init__(self,c,mode=None,behavior=None):
        self.c=c;self.v=c['vehicle'];self.mode=mode or self.v['mode'];self.behavior=behavior or self.v['shuttle_behavior']
        key=self.mode+str(self.v['grid_route']) if self.mode=='grid' else ('shuttle_reverse' if self.behavior=='reverse' else 'shuttle_uturn') if self.mode=='shuttle' else 'loop'
        self.path=paths(c)[key];self.key=key;self.center=-28;self.shuttle_half=5.5
        self.acc=self.v['max_acceleration_mps2']/2
        radius=4 if self.mode=='loop' else 1.4 if self.mode=='grid' else 1.5
        self.speed=min(self.v['speed_mps'],math.sqrt(self.acc*radius));self.ramp=self.speed/self.acc
        self.dt=c['steering']['integration_dt_s'];self.L=.44;self.T=.47
        self.limit=min(math.radians(30),math.atan(self.L/(self.L/math.tan(math.radians(35))+self.T/2)))
        self.rate=math.radians(25);s=self.v['initial_route_s_m'];i=int(s/self.path.ds)%len(self.path.xy)
        initial=np.zeros(15);initial[:3]=self.path.poses[i];initial[:2]=self.path.at(s);initial[5]=s;initial[11]=1
        if self.key=='shuttle_reverse':initial[0]=5.5;initial[2]=math.pi;initial[11]=-1
        self.cache=[initial]
    def advance(self,a,dt):
        b=a.copy();x,y,yaw,v,delta,s=a[:6]
        if self.key=='shuttle_reverse':
            remaining=5.5-x if a[11]>0 else x+5.5
            desired=-a[11]*min(self.speed,math.sqrt(max(0,2*self.acc*(remaining-.002))))
            if a[10]>0:
                desired=0;b[10]=max(0,a[10]-dt)
                if b[10]==0:b[11]=-a[11]
            elif remaining<.003 and abs(v)<.015:
                desired=0
                if abs(v)<1e-9:b[10]=self.v['stop_duration_s']
            target_delta=0.;error=abs(y)
        else:
            # Restrict nearest search to local route progress: no intersection branch jumps.
            index=int(s/self.path.ds);indices=np.arange(index-8,index+25)
            points=self.path.xy[indices%len(self.path.xy)]
            dist=np.sum((points-[x,y])**2,axis=1);nearest=int(np.argmin(dist))
            ns=indices[nearest]*self.path.ds
            b[5]=max(s-.05,ns);error=math.sqrt(float(dist[nearest]))
            goal=self.path.at(b[5]+self.c['steering']['lookahead_m']);dx,dy=goal-[x,y]
            local_y=-math.sin(yaw)*dx+math.cos(yaw)*dy
            target_delta=math.atan2(2*self.L*local_y,dx*dx+dy*dy)
            desired=self.speed
            if self.key=="shuttle_uturn":
                # Brake before each turn bay; long straight legs retain requested speed.
                q=self.path.at(b[5]+max(.8,self.speed*self.speed/(2*self.acc)))
                if abs(q[0])>5.3:desired=.65*self.speed
            # Lateral acceleration budget uses actual steering, including feedback transients.
            cap=math.sqrt(self.acc/max(abs(math.tan(delta)/self.L),1e-8))
            desired=min(desired,cap)
        target_delta=clip(target_delta,-self.limit,self.limit)
        new_delta=delta+clip(target_delta-delta,-self.rate*dt,self.rate*dt)
        new_v=v+clip(desired-v,-self.acc*dt,self.acc*dt)
        vm=(v+new_v)/2;dm=(delta+new_delta)/2;k=math.tan(dm)/self.L;omega=vm*k
        if abs(omega)>1e-12:
            b[0]=x+(math.sin(yaw+omega*dt)-math.sin(yaw))/k
            b[1]=y+(-math.cos(yaw+omega*dt)+math.cos(yaw))/k
        else:b[0]=x+vm*math.cos(yaw)*dt;b[1]=y+vm*math.sin(yaw)*dt
        b[2]=yaw+omega*dt;b[3]=new_v;b[4]=new_delta
        for j,(xx,yy) in enumerate([(self.L,self.T/2),(self.L,-self.T/2),(0,self.T/2),(0,-self.T/2)]):
            b[6+j]+=vm*math.hypot(1-k*yy,k*xx)*dt/self.v['wheel_radius_m']
        if self.key=='shuttle_reverse':b[5]+=abs(vm)*dt
        b[12]=(new_v-v)/dt;b[13]=(new_delta-delta)/dt;b[14]=error
        return b
    def sample(self,time):
        t=max(0,float(time));index=int((t+1e-9)/self.dt)
        while len(self.cache)<=index:self.cache.append(self.advance(self.cache[-1],self.dt))
        a=self.cache[index];rem=t-index*self.dt
        if rem>1e-8:a=self.advance(a,rem)
        x,y,yaw,v,delta,s=a[:6];co,si=math.cos(yaw),math.sin(yaw);omega=v*math.tan(delta)/self.L
        # Bicycle equations apply at rear axle; body origin is 0.22m ahead.
        return {'position':np.array([x+.22*co-28,y+.22*si,0]),'rear_position':np.array([x-28,y,0]),'yaw':yaw,'speed':abs(v),'longitudinal_speed':v,'velocity':np.array([v*co-.22*omega*si,v*si+.22*omega*co,0]),'direction':1 if v>=0 else -1,'distance':float(a[6]*self.v['wheel_radius_m']),'mode':self.mode,'steering_angle':delta,'steering_rate':a[13],'front_angles':ackermann(delta),'wheel_angles':a[6:10].copy(),'yaw_rate':omega,'acceleration':a[12],'path_progress':s,'tracking_error':a[14]}
