from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
WIDTH, HEIGHT = 1280, 720

def _font(size):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','DejaVuSans-Bold.ttf'):
        try: return ImageFont.truetype(p,size)
        except OSError: pass
    return ImageFont.load_default()

def _wrap(draw,text,font,max_width):
    words=str(text or 'Ambient World').split(); lines=[]; cur=''
    for word in words:
        test=(cur+' '+word).strip()
        if draw.textbbox((0,0),test,font=font)[2] <= max_width: cur=test
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    return lines[:3] or ['Ambient World']

def generate_thumbnail(source_path: str, output_path: str, title: str, label='SOCIALIZED AMBIENT WORLDS') -> str:
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    with Image.open(source_path) as im:
        im=im.convert('RGB'); scale=max(WIDTH/im.width,HEIGHT/im.height)
        im=im.resize((int(im.width*scale),int(im.height*scale)),Image.Resampling.LANCZOS)
        x=(im.width-WIDTH)//2; y=(im.height-HEIGHT)//2; bg=im.crop((x,y,x+WIDTH,y+HEIGHT))
    overlay=Image.new('RGBA',(WIDTH,HEIGHT),(0,0,0,0)); d=ImageDraw.Draw(overlay)
    d.rectangle((0,0,WIDTH,HEIGHT),fill=(0,0,0,70)); d.rectangle((0,0,WIDTH,12),fill=(255,255,255,230))
    d.rectangle((0,HEIGHT-205,WIDTH,HEIGHT),fill=(0,0,0,175)); d.text((52,45),label[:34],font=_font(24),fill='white')
    font=_font(66); lines=_wrap(d,title,font,1110); ty=HEIGHT-170-(len(lines)-1)*8
    for line in lines:
        box=d.textbbox((0,0),line,font=font,stroke_width=3); tx=(WIDTH-(box[2]-box[0]))//2
        d.text((tx,ty),line,font=font,fill='white',stroke_width=3,stroke_fill='black'); ty+=72
    Image.alpha_composite(bg.convert('RGBA'),overlay).convert('RGB').save(output_path,'JPEG',quality=92,optimize=True,progressive=True)
    return output_path
