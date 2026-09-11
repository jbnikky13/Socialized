from __future__ import annotations
import math, random, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

SCENES={'rain','snow','fireplace','candle','forest','cafe'}

def make_scene_overlay(path: Path, scene: str, width=640, height=360, fps=30, seconds=12):
    scene=scene if scene in SCENES else 'rain'
    rng=random.Random({'rain':71337,'snow':91337,'fireplace':32111,'candle':44119,'forest':55121,'cafe':66131}[scene])
    count={'rain':120,'snow':60,'fireplace':48,'candle':24,'forest':34,'cafe':22}[scene]
    particles=[(rng.uniform(0,width),rng.uniform(-height,height),rng.uniform(0.7,3.0),rng.uniform(35,270)) for _ in range(count)]
    frames=path.parent/'scene_frames'; frames.mkdir(exist_ok=True)
    total=int(fps*seconds)
    try:
        for i in range(total):
            t=i/fps; frame=Image.new('RGBA',(width,height),(0,0,0,0)); d=ImageDraw.Draw(frame)
            if scene in ('rain','snow'):
                for x0,y0,size,speed in particles:
                    y=((y0+speed*t)%(height+30))-30
                    x=(x0+(-32 if scene=='rain' else 3)*t)%width
                    if scene=='rain':
                        d.line((x,y,x-size*2.6,y+max(10,size*8)),fill=(205,225,255,125),width=1)
                        if size>2.1: d.line((x+1,y+2,x-size*1.5,y+max(8,size*6)),fill=(235,245,255,70),width=1)
                    else:
                        d.ellipse((x-size,y-size,x+size,y+size),fill=(245,250,255,115))
            elif scene in ('fireplace','candle'):
                cx=width*.5; base=height*.70 if scene=='fireplace' else height*.53
                # Multiple independently pulsing translucent flame blobs create
                # continuous movement instead of a static orange glow.
                for j in range(16 if scene=='fireplace' else 9):
                    phase=t*3.6+j*.73
                    pulse=(math.sin(phase)+1)/2
                    r=(20 if scene=='fireplace' else 10)*(.65+.35*pulse)
                    x=cx+math.sin(phase*1.7+j)*6
                    y=base-r*(1.0+0.45*pulse)
                    d.ellipse((x-r*1.7,y-r,x+r*1.7,y+r),fill=(255,120,35,72))
                    d.ellipse((x-r*.75,y-r*.9,x+r*.75,y+r*.6),fill=(255,220,120,115))
            elif scene=='forest':
                for x,y,size,_ in particles:
                    sway=math.sin(t*1.2+x)*3
                    d.line((x,y,x+sway,y-max(8,size*5)),fill=(210,235,205,45),width=1)
            elif scene=='cafe':
                for j in range(12):
                    x=width*.25+j*width*.055; y=height*.58-((t*8+j*9)%55); r=2+(j%3)*.7
                    d.ellipse((x-r,y-r,x+r,y+r),fill=(235,235,225,32))
            frame.save(frames/f'{i:04d}.png')
        subprocess.run(['ffmpeg','-y','-framerate',str(fps),'-i',str(frames/'%04d.png'),'-c:v','qtrle','-pix_fmt','argb',str(path)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    finally:
        for f in frames.glob('*.png'): f.unlink()
        try: frames.rmdir()
        except OSError: pass
