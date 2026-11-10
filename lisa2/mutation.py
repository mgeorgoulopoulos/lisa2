"""Silhouettes change mutation, never add a silhouette term to fitness."""
import numpy as np
from .geometry import BASES,constrain,project


def outside_any_silhouette(vertices,masks):
    h,w=masks.shape[1:]
    outside=np.zeros(3,dtype=bool)
    for basis,mask in zip(BASES,masks):
        points=project(vertices,basis,w,h)
        for i,(x,y) in enumerate(points):
            if x<0 or x>=w or y<0 or y>=h or not mask[int(y),int(x)]:
                outside[i]=True
    return outside


def adaptive_mutation(individual,centroid,outside,rng):
    """Gate CMA-ES offsets per vertex: bad .90/3x, good .25/1x."""
    parent=np.asarray(centroid).reshape(3,3)
    offsets=np.asarray(individual).reshape(3,3)-parent
    values=parent.copy()
    for i in range(3):
        if rng.random() < (.90 if outside[i] else .25):
            values[i]+=offsets[i]*(3. if outside[i] else 1.)
    individual[:]=values.ravel().tolist()
    return individual
