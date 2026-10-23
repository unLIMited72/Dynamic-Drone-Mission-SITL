"""Simulation-time trajectories. Mocap kinematics, not steering/motor dynamics."""
import math
import numpy as np
from .stadium import StadiumPath

class RoundedGrid:
    """Circular fillets at every intersection, tangent continuous, arc-length sampled."""
    def __init__(self,vertices,radius):
        pts=np.asarray(vertices,float); corners=[]
        for i,p in enumerate(pts):
            incoming=p-pts[i-1]; outgoing=pts[(i+1)%len(pts)]-p
            li=np.linalg.norm(incoming); lo=np.linalg.norm(outgoing)
            u=incoming/li; v=outgoing/lo
            angle=math.acos(np.clip(u@v,-1,1))
            if angle < 1e-6 or angle > math.pi-1e-6:
                raise ValueError('grid route requires nondegenerate turns')
            trim=radius*math.tan(angle/2)
            if trim >= min(li,lo)/2: raise ValueError('grid fillets overlap; reduce turn radius')
            sign=np.sign(np.cross(u,v)); entry=p-u*trim; end=p+v*trim
            center=entry+sign*radius*np.array([-u[1],u[0]])
            theta=math.atan2(*(entry-center)[::-1])
            corners.append((entry,end,center,theta,sign,angle))
        self.parts=[]
        for i,(entry,end,center,theta,sign,angle) in enumerate(corners):
            self.parts.append(('arc',radius*angle,(center,radius,theta,sign)))
            nxt=corners[(i+1)%len(pts)][0]; delta=nxt-end
            self.parts.append(('line',np.linalg.norm(delta),(end,delta/np.linalg.norm(delta))))
        self.length=sum(p[1] for p in self.parts)
    def pose(self,s):
        s%=self.length
        for kind,length,args in self.parts:
            if s <= length:
                if kind=='line':
                    p,u=args; return p+s*u,math.atan2(u[1],u[0])
                center,r,theta,sign=args; theta+=sign*s/r
                return center+r*np.array([math.cos(theta),math.sin(theta)]),theta+sign*math.pi/2
            s-=length
        raise RuntimeError('path sampling')

