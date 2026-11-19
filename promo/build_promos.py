"""Build matching poster PNGs and seek-safe HTML from the published evidence."""
from pathlib import Path
import shutil
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ASSETS=HERE/'assets'
MEDIA=ROOT/'media'
MEDIA.mkdir(exist_ok=True)
room=json.loads((ROOT/'benchmarks/burning-room.json').read_text(encoding='utf-8'))
pressure=json.loads((ROOT/'benchmarks/pressure-test.json').read_text(encoding='utf-8'))
assert not pressure['requested_gpu_oom_rescue_proven']
metrics={m['key']:m for m in room['metrics']}
tex=metrics['texture_allocation'];tri=metrics['mesh_triangles'];timing=metrics['render_time']
p_before=next(x for x in pressure['measurements'] if x['tag']=='stress12288_original_repeat')
p_after=next(x for x in pressure['measurements'] if x['tag']=='stress12288_optimized_repeat')
p_overhead=p_after['analysis_seconds']+p_after['optimization_seconds']
p_reduction=(p_before['cycles_reported_peak_alloc_gib']-p_after['cycles_reported_peak_alloc_gib'])/p_before['cycles_reported_peak_alloc_gib']*100

CSS='''
@font-face{font-family:Display;src:url('assets/BigShoulders-Bold.ttf')}@font-face{font-family:Body;src:url('assets/BricolageGrotesque-Bold.ttf')}@font-face{font-family:Mono;src:url('assets/DMMono-Regular.ttf')}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#111916;color:#f1eddf}#root{position:relative;width:100%;height:100%;overflow:hidden;background:#111916}
.brand{position:absolute;left:40px;top:34px;font:28px Body;letter-spacing:2px}.free{position:absolute;right:40px;top:31px;border:1px solid #789765;border-radius:4px;padding:10px 16px;color:#d5ffa7;font:22px Mono}
h1{position:absolute;left:40px;top:94px;margin:0;font:110px/.91 Display;letter-spacing:-1px}.headline-line{display:block}.viewport{position:absolute;overflow:hidden;--split:0;border:1px solid #4f6556;background:#1d2921}.room-view{left:40px;top:310px;width:1000px;height:667px}.pressure-view{left:40px;top:310px;width:450px;height:800px}.photo{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.after-layer{position:absolute;inset:0;clip-path:inset(0 calc((100 - var(--split))*1%) 0 0)}
.tag{position:absolute;top:18px;left:18px;border-radius:3px;background:#111916;color:#f1eddf;border:1px solid #77946f;padding:10px 14px;font:22px Mono}.before-tag{left:auto;right:18px}.after-tag{color:#d5ffa7}.divider{position:absolute;top:0;bottom:0;left:calc(var(--split)*1%);width:3px;background:#f1eddf;opacity:0}.divider:after{content:'<>';position:absolute;top:50%;left:-20px;width:42px;height:42px;border-radius:50%;background:#d5ffa7;color:#111916;text-align:center;line-height:40px;font-size:29px;font-family:Body}
.stats{position:absolute;top:1000px;left:40px;right:40px;display:grid;grid-template-columns:1.1fr 1.1fr 1fr;gap:28px}.number{font:96px/1 Display;color:#d5ffa7}.stat-label{font:22px Mono;margin-top:12px;line-height:1.35}.cta{position:absolute;left:40px;top:1183px;right:40px;padding-top:20px;border-top:1px solid #536750;font:30px Mono;color:#d5ffa7}.note{position:absolute;left:40px;right:40px;font:21px/1.35 Mono;color:#d0d5c9}.n1{top:1260px}.n2{top:1293px}.pressure-stats{position:absolute;left:540px;top:330px;width:500px}.kicker{font:24px Mono;color:#e0e6da}.pressure-number{font:142px/1 Display;margin-top:9px}.unit{font:40px Body;color:#d1d7cc}.before-value{padding-bottom:30px;border-bottom:1px solid #536750}.after-value{margin-top:30px;color:#d5ffa7}.pressure-reduction{font:63px Display;color:#d5ffa7;margin-top:34px}.pressure-detail{font:25px/1.4 Mono;color:#d0d5c9}.pressure-time{font:38px Display;margin-top:30px}.pressure-prep{font:23px Mono;margin-top:14px}.p1{top:1150px;font-size:25px}.p2{top:1190px;font-size:24px}.p3{top:1232px;font-size:20px}.pressure-cta{top:1272px;font-size:27px}
'''

def composition(kind):
    ident='room' if kind=='room' else 'pressure'
    title='KEEP THE SHOT.<span class="headline-line">CUT THE WASTE.</span>' if kind=='room' else '8 GB CARD.<span class="headline-line">LESS MEMORY.</span>'
    stage=f'''<div class="viewport {kind}-view" id="comparison">
<img class="photo" src="assets/{kind}-before.jpg" alt="Actual before render"/><span class="tag before-tag" data-layout-allow-occlusion>BEFORE</span>
<div class="after-layer"><img class="photo" src="assets/{kind}-after.jpg" alt="Actual optimized render"/><span class="tag after-tag">AFTER</span></div><div class="divider"></div></div>'''
    if kind=='room':
        details=f'''<div class="stats"><div><div class="number">{tex['reduction_percent']:.1f}%</div><div class="stat-label">lower texture allocation</div></div><div><div class="number">{tri['reduction_percent']:.1f}%</div><div class="stat-label">fewer mesh triangles</div></div><div><div class="number">FREE</div><div class="stat-label">source + demo files</div></div></div>
<div class="cta">github.com/ma3maro/vram-fixer</div><div class="note n1">Blender 5.3 / RTX 4060 Ti / Strong / 1920×1280</div><div class="note n2">Texture allocation is not total VRAM. Scene-specific result.</div>'''
    else:
        details=f'''<div class="pressure-stats"><div class="before-value"><div class="kicker">BEFORE / CYCLES ALLOCATION</div><div class="pressure-number">{p_before['cycles_reported_peak_alloc_gib']:.2f}<span class="unit"> GiB</span></div></div><div class="after-value"><div class="kicker">AFTER / CYCLES ALLOCATION</div><div class="pressure-number">{p_after['cycles_reported_peak_alloc_gib']:.2f}<span class="unit"> GiB</span></div></div><div class="pressure-reduction">{p_reduction:.1f}% LOWER</div><div class="pressure-detail">on an 8 GB RTX 4060 Ti</div><div class="pressure-time">{p_before['render_seconds']:.2f}s to {p_after['render_seconds']:.2f}s render</div><div class="pressure-prep">+{p_overhead:.2f}s preparation</div></div><div class="note p1">Cycles allocation includes host RAM.</div><div class="note p2">BEFORE already rendered using system RAM.</div><div class="note p3">12K stress assets / 32 samples / No hard-OOM rescue claim.</div><div class="cta pressure-cta">FREE: github.com/ma3maro/vram-fixer</div>'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=1080,height=1350"/><title>VRAM Fixer / {ident} comparison</title><script src="assets/gsap.min.js"></script><style>{CSS}</style></head><body>
<div id="root" data-composition-id="{ident}" data-width="1080" data-height="1350" data-duration="8"><div class="brand">VRAM FIXER</div><div class="free">FREE / OPEN SOURCE</div><h1>{title}</h1>{stage}{details}</div>
<script>
// Image-aligned wipe adapted from the before-after-wipe registry primitive.
const stage=document.getElementById('comparison');const divider=document.querySelector('.divider');
const tl=gsap.timeline({{paused:true}});
tl.fromTo(stage,{{'--split':0}},{{'--split':100,duration:2,ease:'sine.inOut'}},1.2);
tl.fromTo(divider,{{opacity:0}},{{opacity:1,duration:.12}},1.2);tl.to(divider,{{opacity:0,duration:.12}},3.08);
tl.fromTo(stage,{{'--split':100}},{{'--split':0,duration:2,ease:'sine.inOut',immediateRender:false}},5.2);
tl.fromTo(divider,{{opacity:0}},{{opacity:1,duration:.12,immediateRender:false}},5.2);tl.to(divider,{{opacity:0,duration:.12}},7.08);
window.__timelines['{ident}']=tl;
</script></body></html>'''
(HERE/'index.html').write_text(composition('room'),encoding='utf-8')
pressure_project=ROOT/'promo-pressure'
(pressure_project/'assets').mkdir(parents=True,exist_ok=True)
for asset in ASSETS.iterdir():
    if asset.is_file():shutil.copy2(asset,pressure_project/'assets'/asset.name)
(pressure_project/'index.html').write_text(composition('pressure'),encoding='utf-8')

# Still cards: original images, identical treatment on both comparison sides.
BG='#111916';FG='#f1eddf';ACC='#d5ffa7';MUTED='#c8d0c1'
def font(size,face='body'):
    file={'body':'BricolageGrotesque-Bold.ttf','display':'BigShoulders-Bold.ttf','mono':'DMMono-Regular.ttf'}[face]
    return ImageFont.truetype(str(ASSETS/file),size)

def txt(draw,position,text,size=26,color=FG,face='body',max_width=None):
    f=font(size,face)
    if max_width:
        while draw.textlength(text,font=f)>max_width and size>12:
            size-=1;f=font(size,face)
    x,y=position;box=draw.textbbox((x,y),text,font=f,anchor='lt')
    assert box[0]>=0 and box[2]<=1200 and box[3]<=1350,(text,box)
    draw.text((x,y),text,font=f,fill=color,anchor='lt')

def base():
    im=Image.new('RGB',(1200,1350),BG);d=ImageDraw.Draw(im)
    txt(d,(44,38),'VRAM FIXER',31)
    d.rounded_rectangle((916,28,1156,82),radius=3,outline='#79976a',width=2)
    txt(d,(935,43),'100% FREE',26,ACC,'mono')
    return im,d

def photo(im,name,box):
    source=Image.open(ASSETS/name).convert('RGB')
    fitted=ImageOps.contain(source,(box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
    x=box[0]+((box[2]-box[0])-fitted.width)//2;y=box[1]+((box[3]-box[1])-fitted.height)//2
    im.paste(fitted,(x,y))

def cta(d,y=1290):txt(d,(44,y),'FREE / github.com/ma3maro/vram-fixer',25,ACC,'mono',1112)

im,d=base();txt(d,(44,115),'SAME SHOT.',119,FG,'display');txt(d,(44,229),'LESS MEMORY.',119,FG,'display')
photo(im,'room-after.jpg',(40,357,1160,1104))
for x,value,label in [(44,f"{tex['reduction_percent']:.1f}%",'lower texture allocation'),(438,f"{tri['reduction_percent']:.1f}%",'fewer mesh triangles'),(841,'FREE','source + demo scenes')]:
    txt(d,(x,1124),value,76,ACC,'display');txt(d,(x,1210),label,21,FG,'mono',330)
txt(d,(44,1253),'Texture allocation is not total VRAM. Measured on this demo.',21,MUTED,'mono',1112);cta(d)
im.save(MEDIA/'01-launch.png')

im,d=base();txt(d,(44,120),'SPOT THE DIFFERENCE.',105,FG,'display',1112)
txt(d,(44,250),'Same camera. Same lighting. Same render settings.',30)
for index,(image,value,tris,secs) in enumerate([('room-before.jpg',tex['before'],tri['before'],timing['before']),('room-after.jpg',tex['after'],tri['after'],timing['after'])]):
    x=44+index*580
    txt(d,(x,318),'BEFORE' if index==0 else 'AFTER',27,ACC if index else FG,'mono')
    photo(im,image,(x,365,x+532,720))
    txt(d,(x,758),f'{value:,.2f} MiB',62,ACC if index else FG,'display',532)
    txt(d,(x,837),'Cycles texture allocation',24,FG,'mono')
    txt(d,(x,906),f'{tris:,} mesh triangles',34,FG,'body',532)
    txt(d,(x,970),f'{secs:.2f}s render',44,FG,'display')
d.line((44,1055,1156,1055),fill='#52654e',width=2)
txt(d,(44,1090),'262 protected objects / 10 textures + 22 meshes optimized',25,FG,'mono',1112)
txt(d,(44,1144),f"+{room['core_preparation_seconds']:.2f}s preparation. Two runs per version.",24,MUTED,'mono',1112)
txt(d,(44,1191),'Texture allocation is not total VRAM. Scene-specific results.',23,MUTED,'mono',1112)
txt(d,(44,1236),'Blender 5.3 / RTX 4060 Ti / Strong / 1920×1280',22,MUTED,'mono',1112);cta(d)
im.save(MEDIA/'02-burning-room-before-after.png')

im,d=base();txt(d,(44,122),'8 GB GPU.',131,FG,'display');txt(d,(44,247),'LESS SPILL. MORE HEADROOM.',88,FG,'display',1112)
for index,(image,value,secs) in enumerate([('pressure-before.jpg',p_before['cycles_reported_peak_alloc_gib'],p_before['render_seconds']),('pressure-after.jpg',p_after['cycles_reported_peak_alloc_gib'],p_after['render_seconds'])]):
    x=44+index*580
    txt(d,(x,366),'BEFORE' if index==0 else 'AFTER',26,ACC if index else FG,'mono')
    txt(d,(x,411),f'{value:.2f} GiB',77,ACC if index else FG,'display')
    photo(im,image,(x,510,x+532,1120))
    txt(d,(x,1139),f'{secs:.2f}s render',32,FG,'body')
txt(d,(44,1190),'Cycles allocation includes host RAM. BEFORE already rendered.',24,MUTED,'mono',1112)
txt(d,(44,1232),f"12K stress assets / 32 samples / +{p_overhead:.2f}s preparation",23,MUTED,'mono',1112);cta(d)
im.save(MEDIA/'03-8gb-pressure-test.png')
print('Promo HTML and three poster PNGs created from evidence. No comparison image grading applied.')
