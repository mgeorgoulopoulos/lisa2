"""Exactly reconstructible full-size Laplacian scale-space decomposition."""
import numpy as np
from scipy.ndimage import gaussian_filter


def decompose(images,sigmas=(16.,8.,4.,2.,0.)):
    if sigmas[-1]!=0 or any(a<=b for a,b in zip(sigmas,sigmas[1:])):
        raise ValueError('Blur scales must strictly decrease to zero')
    cumulative=[gaussian_filter(images,(0,s,s,0),mode='reflect') if s else images.copy() for s in sigmas]
    bands=[cumulative[0]]+[b-a for a,b in zip(cumulative,cumulative[1:])]
    return np.array(bands),np.array(cumulative)


def pool(image,factor):
    if factor==1: return image
    v,h,w,c=image.shape
    if h%factor or w%factor: raise ValueError('Pool factor must divide the image')
    return image.reshape(v,h//factor,factor,w//factor,factor,c).mean(axis=(2,4))


def pooled_weights(weights,factor):
    v,h,w=weights.shape
    return weights.reshape(v,h//factor,factor,w//factor,factor).sum(axis=(2,4))
