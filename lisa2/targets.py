"""Reproducible original vector artwork; no downloaded or licensed images."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

NAMES = ['orbit', 'eye', 'sun', 'lotus']


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    scale = 3
    def point(x, y): return (int(x * scale), int(y * scale))
    for index, name in enumerate(NAMES):
        mask = Image.new('L', (320 * scale, 240 * scale))
        d = ImageDraw.Draw(mask)
        def ellipse(box, width=6):
            d.ellipse(tuple(int(x * scale) for x in box), outline=255, width=width * scale)
        def line(points, width=6):
            d.line([point(*p) for p in points], fill=255, width=width * scale, joint='curve')
        if index == 0:
            ellipse((107, 67, 213, 173))
            ellipse((78, 100, 242, 140), 5)
            d.ellipse((180*scale, 67*scale, 195*scale, 82*scale), fill=255)
        elif index == 1:
            a = np.linspace(0, 2*np.pi, 150)
            line([(160+83*np.cos(t), 120+40*np.sin(t)*abs(np.sin(t))) for t in a])
            ellipse((134, 94, 186, 146))
            d.ellipse((153*scale, 113*scale, 167*scale, 127*scale), fill=255)
        elif index == 2:
            ellipse((126, 86, 194, 154))
            for t in np.linspace(0, 2*np.pi, 12, endpoint=False):
                line([(160+r*np.cos(t),120+r*np.sin(t)) for r in (48, 68)], 5)
        else:
            line([(83,146),(237,146)], 5)
            for center,rx,ry in [(130,31,38),(190,31,38),(160,26,62)]:
                a=np.linspace(0, np.pi, 80)
                line([(center+rx*np.cos(t),147-ry*np.sin(t)) for t in a], 5)
            line([(130,147),(160,164),(190,147)], 5)
        mask = mask.resize((320,240), Image.Resampling.LANCZOS)
        glow = mask.filter(ImageFilter.GaussianBlur(3))
        intensity = np.maximum(np.array(mask)*.75, np.array(glow)*.7) / 255.
        # Same chromaticity permits additive contributions to cooperate.
        rgb = intensity[:,:,None] * np.array([1., .55, .19])
        Image.fromarray(np.uint8(np.clip(rgb,0,1)*255)).save(directory/f'{index+1}_{name}.png')


def load(paths, width=128, height=96):
    if len(paths) != 4:
        raise ValueError('Exactly four images are required')
    result=[]
    for p in paths:
        im=Image.open(p).convert('RGB')
        # Contain, never stretch a user image; unused pixels are black.
        im=ImageOps.contain(im,(width,height),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(width,height))
        canvas.paste(im,((width-im.width)//2,(height-im.height)//2))
        result.append(np.asarray(canvas,dtype=np.float64)/255.)
    return np.array(result)
