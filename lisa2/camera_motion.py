"""Preview-only orbit/dolly camera; training cameras and model stay unchanged."""
import numpy as np
from numba import njit
from scipy.spatial.transform import Rotation,Slerp
from .geometry import RADIUS
from .raster import render

DURATION=3.6
MIN_RADIUS=.95
NEAR=.12

class CameraMove:
    def __init__(self,start_basis,end_basis,start_radius=RADIUS,min_radius=MIN_RADIUS):
        self.start=np.array(start_basis);self.end=np.array(end_basis)
        self.start_radius=float(start_radius);self.minimum=float(min_radius)
        self.rotation=Slerp([0.,1.],Rotation.from_matrix(np.array([self.start.T,self.end.T])))

    def at(self,t):
        t=float(np.clip(t,0,1))
        if t==0: return self.start.copy(),self.start_radius
        if t==1: return self.end.copy(),RADIUS
        e=t*t*t*(10+t*(-15+6*t))
        b=self.rotation(e).as_matrix().T
        envelope=np.sin(np.pi*e)**4
        distance=(1-e)*self.start_radius+e*RADIUS
        distance=distance+(self.minimum-distance)*envelope
        # A restrained bank emphasizes the fly-through, and vanishes at endpoints.
        angle=np.deg2rad(5)*np.sin(2*np.pi*e)*np.sin(np.pi*e)**2
        right=b[0].copy();up=b[1].copy()
        b[0]=np.cos(angle)*right+np.sin(angle)*up
        b[1]=-np.sin(angle)*right+np.cos(angle)*up
        return b,distance


@njit(cache=True)
def clipped_mesh(vertices,colors,basis,radius,near=NEAR):
    # Clip in world space before perspective division. A clipped triangle can
    # become a quad; both fan triangles retain interpolated vertex RGB.
    output=np.empty((len(vertices)*2,3,3));rgb=np.empty_like(output);count=0
    for i in range(len(vertices)):
        points=np.empty((4,3));values=np.empty((4,3));n=0
        previous=vertices[i,2];previous_color=colors[i,2]
        previous_depth=radius-np.dot(previous,basis[2])
        for j in range(3):
            point=vertices[i,j];color=colors[i,j];depth=radius-np.dot(point,basis[2])
            if (depth>=near)!=(previous_depth>=near):
                fraction=(near-previous_depth)/(depth-previous_depth)
                points[n]=previous+fraction*(point-previous)
                values[n]=previous_color+fraction*(color-previous_color);n+=1
            if depth>=near:
                points[n]=point;values[n]=color;n+=1
            previous=point;previous_color=color;previous_depth=depth
        # Anchor clipped quads geometrically, so reversing input winding uses
        # the same diagonal (important for affine RGB interpolation).
        anchor=0
        for j in range(1,n):
            for axis in range(3):
                delta=points[j,axis]-points[anchor,axis]
                if abs(delta)>1e-10:
                    if delta<0: anchor=j
                    break
        for j in range(1,n-1):
            a=anchor;b=(anchor+j)%n;c=(anchor+j+1)%n
            output[count,0]=points[a];output[count,1]=points[b];output[count,2]=points[c]
            rgb[count,0]=values[a];rgb[count,1]=values[b];rgb[count,2]=values[c];count+=1
    # Existing renderer's camera has fixed RADIUS. This translation is exactly
    # equivalent to moving its eye radially; the stored model is never altered.
    for i in range(count):
        for j in range(3): output[i,j]+=(RADIUS-radius)*basis[2]
    return output[:count],rgb[:count]


def render_camera(vertices,colors,basis,width=640,radius=RADIUS):
    basis=np.ascontiguousarray(basis)
    if radius==RADIUS:
        return render(vertices,colors,width,width*3//4,basis[None])[0]
    colors=np.asarray(colors)
    if colors.ndim==2: colors=np.repeat(colors[:,None,:],3,axis=1)
    v,c=clipped_mesh(np.asarray(vertices),colors,basis,radius)
    return render(v,c,width,width*3//4,basis[None])[0]
