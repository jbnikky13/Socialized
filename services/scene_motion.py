from __future__ import annotations
import math, random, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

SCENES={'rain','snow','fireplace','candle','forest','cafe'}

def make_scene_overlay(path: Path, scene: str, width=640, height=360, fps=30, seconds=12):
    scene=scene if scene in SCENES else 'rain'
    rng=random.Random({'rain':71337,'snow':91337,'fireplace':32111,'candle':44119,'forest':55121,'cafe':66131}[scene])
    count={'rain':80,'snow':45,'fireplace':35,'candle':18,'forest':28,'cafe':18}[scene]
    particles=[(rng.uniform(0,width),rng.uniform(-height,height),rng.uniform(0.7,3.0),rng.uniform(35,270)) for _ in range(count)]
    frames=path.parent/'scene_frames'; frames.mkdir(exist_ok=True)
    total=int(fps*seconds)
    try:
        for i in range(total):
            t=i/fps; frame=Image.new('RGBA',(width,height),(0,0,0,0)); d=ImageDraw.Draw(frame)
            if scene in ('rain','snow'):
                for x0,y0,size,speed in particles:
                    y=((y0+speed*t)%(height+24))-24
                    x=(x0+(-28 if scene=='rain' else 3)*t)%width
                    if scene=='rain': d.line((x,y,x-size*3,y+max(8,size*7)),fill=(205,225,255,90),width=1)
                    else: d.ellipse((x-size,y-size,x+size,y+size),fill=(245,250,255,90))
            elif scene in ('fireplace','candle'):
                cx=width*.5; base=height*.68 if scene=='fireplace' else height*.52
                for j in range(12 if scene=='fireplace' else 7):
                    phase=t*3.2+j*.8; pulse=(math.sin(phase)+1)/2
                    r=(18 if scene=='fireplace' else 9)*(.7+.3*pulse)
                    x=cx+math.sin(phase*1.7+j)*5; y=base-r*1.2
                    d.ellipse((x-r*1.5,y-r,x+r*1.5,y+r),fill=(255,150,55,60))
                    d.ellipse((x-r*.7,y-r*.8,x+r*.7,y+r*.6),fill=(255,220,130,90))
            elif scene=='forest':
                for x,y,size,_ in particles:
                    sway=math.sin(t*1.2+x)*3
                    d.line((x,y,x+sway,y-max(8,size*5)),fill=(210,235,205,35),width=1)
            elif scene=='cafe':
                for j in range(10):
                    x=width*.25+j*width*.055; y=height*.58-((t*8+j*9)%55); r=2+(j%3)*.7
                    d.ellipse((x-r,y-r,x+r,y+r),fill=(235,235,225,25))
            frame.save(frames/f'{i:04d}.png')
        subprocess.run(['ffmpeg','-y','-framerate',str(fps),'-i',str(frames/'%04d.png'),'-c:v','qtrle','-pix_fmt','argb',str(path)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    finally:
        for f in frames.glob('*.png'): f.unlink()
        try: frames.rmdir()
        except OSError: pass
