import numpy as np
import torch
from lisa2.gradient_trial import soft_render
from lisa2.geometry import BASES,project

torch.set_num_threads(1)
v=torch.tensor([[[-.321,-.211,.097],[.437,-.173,.213],[.051,.367,-.157]]],dtype=torch.float64,requires_grad=True)
c=torch.tensor([[.23,.17,.09]],dtype=torch.float64,requires_grad=True)
assert torch.autograd.gradcheck(lambda a,b:soft_render(a,b,32,.7,use_checkpoint=False),(v,c),atol=1e-4,rtol=1e-3)
actual=soft_render(v,c,32,.00001,use_checkpoint=False).detach().numpy()
expected=np.zeros_like(actual)
y,x=np.mgrid[:24,:32];x=x+.5;y=y+.5
for k,basis in enumerate(BASES):
    p=project(v.detach().numpy()[0],basis,32,24)
    edges=[]
    for a,b in [(p[0],p[1]),(p[1],p[2]),(p[2],p[0])]:
        edges.append((b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]))
    inside=((edges[0]>=0)&(edges[1]>=0)&(edges[2]>=0))|((edges[0]<=0)&(edges[1]<=0)&(edges[2]<=0))
    expected[k,inside]=c.detach().numpy()[0]
assert np.max(np.abs(actual-expected))<1e-6
print('PASS: joint-render finite-difference gradients and hard-raster limit in all four perspective cameras.')
print('CUDA:',torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')

full=soft_render(v,c,32,.7,use_checkpoint=False).square().sum()
g1=torch.autograd.grad(full,(v,c))
partials=sum(soft_render(v,c,32,.7,use_checkpoint=False,camera_indices=[k]).square().sum() for k in range(4))
g2=torch.autograd.grad(partials,(v,c))
assert all(torch.allclose(a,b,atol=1e-10) for a,b in zip(g1,g2))
print('PASS: per-camera gradient accumulation equals the full joint objective.')
