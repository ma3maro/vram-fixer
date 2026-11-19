"""Package clean artwork and calculate publishable, qualified metrics from real logs."""
from pathlib import Path
import csv
import json
import re
import shutil
import statistics
import struct
from PIL import Image, ImageStat, ImageChops, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
OUT=HERE/'SHOWCASE';OUT.mkdir(exist_ok=True)
TAGS=['before_full_01','after_full_01','before_full_02','after_full_02']
runs=[]
for tag in TAGS:
    receipt=json.loads((HERE/(tag+'_summary.json')).read_text(encoding='utf-8'))
    assert receipt['exit_code']==0 and receipt['watchdog_reason'] is None
    assert receipt['image_validation']['nonblank']
    log=(HERE/(tag+'.log')).read_text(encoding='utf-8',errors='replace')
    peaks=[int(x.replace(',','')) for x in re.findall(r'\|\s+Peak:\s+([\d,]+)',log)]
    image=int(re.findall(r'Total image memory:.*?\(([\d,]+)\)',log)[-1].replace(',',''))
    geom=int(re.findall(r'Total memory:.*?\(([\d,]+)\)',log)[0].replace(',',''))
    runs.append({'tag':tag,'variant':'before' if tag.startswith('before') else 'after',
                 'render_seconds':receipt['worker']['render_seconds'],'cycles_peak_allocation_bytes':max(peaks),
                 'cycles_image_allocation_bytes':image,'cycles_geometry_report_bytes':geom,
                 'sampled_global_gpu_peak_mib':receipt['peak_global_gpu_mib'],
                 'initial_global_gpu_mib':receipt['initial_global_gpu_mib'],
                 'sampled_process_rss_peak_mib':receipt['peak_rss_mib'],
                 'settings':receipt['worker']})
fields=['resolution','samples','adaptive','threshold','seed','exposure','camera_matrix']
for field in fields:
    assert all(r['settings'][field]==runs[0]['settings'][field] for r in runs),field+' differs'
assert all(r['settings']['devices']==[['NVIDIA GeForce RTX 4060 Ti','OPTIX']] for r in runs)
opt=json.loads((HERE/'optimize_final.json').read_text(encoding='utf-8'))
validation=json.loads((HERE/'validation.json').read_text(encoding='utf-8'))
assert validation['pass']
metrics=[]
def metric(key,label,unit,before,after,qualification):
    row={'key':key,'label':label,'unit':unit,'before':before,'after':after,
         'reduction_percent':(before-after)/before*100,'qualification':qualification}
    metrics.append(row);return row

def avg(variant,key):return statistics.mean(r[key] for r in runs if r['variant']==variant)
metric('texture_allocation','Cycles image/texture allocation','MiB',avg('before','cycles_image_allocation_bytes')/2**20,avg('after','cycles_image_allocation_bytes')/2**20,'Native Cycles image allocation report; not total dedicated GPU VRAM.')
metric('cycles_allocation','Cycles reported peak allocation','MiB',avg('before','cycles_peak_allocation_bytes')/2**20,avg('after','cycles_peak_allocation_bytes')/2**20,'Native Cycles allocation report; can include mapped host memory and excludes driver/compositor overhead.')
metric('gpu_global','Sampled global GPU peak, mean of two runs','MiB',avg('before','sampled_global_gpu_peak_mib'),avg('after','sampled_global_gpu_peak_mib'),'nvidia-smi sampled global total, including Windows/apps; not isolated per-process VRAM. Desktop usage varied between runs.')
metric('mesh_triangles','Evaluated mesh triangles','triangles',opt['measured_mesh_triangles_before'],opt['measured_mesh_triangles_after'],'Meshes only. Native curves/text are excluded. Source geometry remains intact; modifiers are reversible.')
metric('geometry_allocation','Cycles geometry memory report','MiB',avg('before','cycles_geometry_report_bytes')/2**20,avg('after','cycles_geometry_report_bytes')/2**20,'Native Cycles geometry statistics, not total scene/driver memory.')
metric('render_time','Render call, mean of two fresh-process runs','seconds',avg('before','render_seconds'),avg('after','render_seconds'),'Includes synchronization, rendering, denoising, identical optical-glow compositor and PNG output. Excludes optimization; only two runs, small timing difference.')
metric('host_ram','Sampled process RSS peak, mean of two runs','MiB',avg('before','sampled_process_rss_peak_mib'),avg('after','sampled_process_rss_peak_mib'),'Freshly opened before/after scenes; does not include the separate optimization-process peak.')
metric('blend_size','Packed Blender file size','MiB',(HERE/'burning_room_before.blend').stat().st_size/2**20,(HERE/'burning_room_after.blend').stat().st_size/2**20,'Negative reduction means growth. After retains originals for Restore; do not claim smaller files.')
lookup={m['key']:m for m in metrics}
core_overhead=opt['analysis_seconds']+opt['application_and_save_seconds']
job_overhead=json.loads((HERE/'optimize_final_summary.json').read_text(encoding='utf-8'))['wall_seconds']

before=Image.open(HERE/'before_full_02.png').convert('RGB')
after=Image.open(HERE/'after_full_02.png').convert('RGB')
diff=ImageChops.difference(before,after)
mean_error=statistics.mean(ImageStat.Stat(diff).mean)/255
quality={'normalized_display_rgb_mae':mean_error,'meaning':'Pixel difference at final camera; not a perceptual guarantee or proof of zero quality loss.'}
for source,name in [('burning_room_before.blend','01_Burning_Room_BEFORE.blend'),('burning_room_after.blend','02_Burning_Room_AFTER.blend'),('before_full_02.png','03_Beauty_BEFORE_16bit.png'),('after_full_02.png','04_Beauty_AFTER_16bit.png')]:
    shutil.copy2(HERE/source,OUT/name)
for file in ('03_Beauty_BEFORE_16bit.png','04_Beauty_AFTER_16bit.png'):
    header=(OUT/file).read_bytes()[:32]
    assert header[24]==16,'Expected original 16-bit PNG'

# Simple scientific comparison; clean renders above have no baked labels/stats.
comparison=Image.new('RGB',(1920,690),'#181b1b')
for index,im in enumerate((before,after)):
    thumb=im.resize((960,640),Image.Resampling.LANCZOS)
    comparison.paste(thumb,(index*960,50))
draw=ImageDraw.Draw(comparison)
try:
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
except OSError:font=ImageFont.load_default()
draw.text((22,13),'BEFORE  |  original assets',font=font,fill='#e8e4d9')
draw.text((982,13),'AFTER  |  same camera, lighting and render settings',font=font,fill='#e8e4d9')
comparison.save(OUT/'05_Before_After_Comparison.jpg',quality=96)
# Same pixel crop, no new camera/re-optimization: inspect the protected hero.
box=(540,340,1000,1060)
before.crop(box).save(OUT/'06_Protected_Dog_Detail_BEFORE.png')
after.crop(box).save(OUT/'07_Protected_Dog_Detail_AFTER.png')
diff.point(lambda x:min(255,x*12)).save(OUT/'08_Difference_x12.png')

report={'scene':'KEEP THE SHOT | Burning Room','blender':'5.3.0','gpu':'NVIDIA GeForce RTX 4060 Ti 8GB','backend':'OptiX GPU only',
        'render_settings':{key:runs[0]['settings'][key] for key in fields},'metrics':metrics,'runs':runs,
        'analysis_seconds':opt['analysis_seconds'],'application_validation_save_seconds':opt['application_and_save_seconds'],
        'core_preparation_seconds':core_overhead,'full_optimization_process_seconds':job_overhead,
        'textures_changed':opt['textures_changed'],'meshes_changed':opt['meshes_changed'],
        'quality':quality,'validation':validation,
        'disclosure':'Controlled demonstration with intentionally oversized 8K/4K procedural bakes. Results are scene/hardware/preset specific. No hard-OOM rescue or universal speedup was proven.'}
(OUT/'metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
with (OUT/'metrics.csv').open('w',newline='',encoding='utf-8-sig') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)

rows=['# Measured before/after results','',
      'Blender 5.3.0 · RTX 4060 Ti 8GB · OptiX GPU only · 1920×1280 · 192 max samples · adaptive threshold .018 · denoising on · Strong preset.',
      'Two fresh-process runs per version; camera, lighting, exposure, seed, resolution and render settings checked identical. No product-code modifications.','',
      '| Measurement | Before | After | Reduction |','|---|---:|---:|---:|']
for m in metrics:
    if m['unit']=='triangles':a=f"{m['before']:,}";b=f"{m['after']:,}"
    else:a=f"{m['before']:.2f} {m['unit']}";b=f"{m['after']:.2f} {m['unit']}"
    rows.append(f"| {m['label']} | {a} | {b} | {m['reduction_percent']:.2f}% |")
rows+=['','## Time overhead',f'- Analysis: {opt["analysis_seconds"]:.2f}s.',f'- Apply + mesh validation/counting + save: {opt["application_and_save_seconds"]:.2f}s.',f'- Combined measured core preparation: {core_overhead:.2f}s.',f'- Complete optimization subprocess including startup/load/checks/shutdown: {job_overhead:.2f}s.',
       '- The before/after render timings exclude preparation. A single optimize-and-render workflow takes longer overall in this demo.',
       '- Render-time difference is small (~3.5% over two runs), not strong evidence of a general performance improvement. Memory reduction is the primary demonstrated benefit.','',
       '## Definitions and limitations']
for m in metrics:rows.append(f'- **{m["label"]}:** {m["qualification"]}')
rows+=['',f'- Normalized display-RGB mean absolute pixel difference: {mean_error:.8f}; small, nonzero differences exist. Do not claim zero quality loss.',
       '- Oversized source bakes and dense small props are deliberate demo choices. No guarantee every customer scene achieves these percentages.',
       '- Protected mascot, cup, flames and smoke: 262 objects checked unchanged. AFTER Restore was tested after reopening; it matched BEFORE object transforms, source meshes, lights, image dimensions/colorspaces and settings.',
       '- Scene is a fully editable still composition. Flames are sculpted 3D emission/transparency geometry; smoke uses real volume shading. It is not a baked Mantaflow simulation or an animation package.',
       '- The AFTER .blend is larger because it preserves originals for Restore. No file-size reduction is advertised.']
(OUT/'MEASUREMENTS.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')

tex=lookup['texture_allocation']['reduction_percent'];tris=lookup['mesh_triangles']['reduction_percent'];alloc=lookup['cycles_allocation']['reduction_percent']
readme=f'''# Burning Room — editable 3D showcase

## Open these

- **01_Burning_Room_BEFORE.blend** — original source assets; select the dog's torso and use N → VRAM Fixer.
- **02_Burning_Room_AFTER.blend** — optimized, with persistent Restore records. Both files contain packed textures; no external art downloads are needed.
- **03 / 04 Beauty PNGs** — clean 1920×1280 **16-bit RGBA** renders for your own graphic design.
- **05 Before/After Comparison.jpg** — quick visual comparison.
- **06 / 07 Protected Dog Detail** — identical crops from the full renders, not a separately optimized camera.
- **08 Difference x12.png** — amplified pixel differences, not an error-free/identical-quality claim.
- **metrics.csv / metrics.json / MEASUREMENTS.md** — actual figures, definitions and raw per-run numbers.

## What is inside

656 native objects: an original sleepy felt dog with fedora, coffee and hand-thrown ceramic cup, woven chair, turned oak table, full wood/plaster room, window and curtain folds, books, detailed pottery, scorched beams, debris, 3D sculpted fire, sparks and volume smoke. Fourteen packed original material bakes. Named collections make editing easy.

The mascot, coffee, fire and smoke are explicitly protected. Strong optimized **10 textures and 22 meshes** while retaining source data. Validation confirmed all 262 protected objects unchanged. Background props use real geometry, including dense lathed fluted pottery.

The optional editable speech balloon is in collection **08 | OPTIONAL SPEECH**, disabled for the clean renders. Enable that collection in the Outliner if wanted. Lighting and camera are in collection 07. The optical-glow compositor is standard Blender 5.3, not an external effect.

## Honest figures you can build a design around

- **{tex:.1f}% lower Cycles texture allocation** in this controlled demo.
- **{tris:.1f}% fewer evaluated mesh triangles** (curves/text excluded).
- **{alloc:.1f}% lower Cycles-reported peak allocation** — not the same thing as dedicated GPU VRAM.
- Render calls averaged **{lookup['render_time']['before']:.2f}s → {lookup['render_time']['after']:.2f}s**, excluding **{core_overhead:.2f}s** core preparation / **{job_overhead:.2f}s** complete optimization job.

Do not label the texture percentage as total VRAM saved. Global GPU samples are included in the detailed report but include Windows/apps and sampling uncertainty. Do not advertise a universal speedup, zero quality loss, guaranteed OOM recovery, or smaller blend files. This demo does not prove those claims.

## Recording a product walkthrough

1. Open BEFORE, enter the active camera view, show the reference torso and Never Touch list.
2. Show the original render. The original 8K/4K bakes intentionally represent oversized production assets.
3. Show Analyze / the detailed report, then Fix VRAM. On-screen MiB is an estimate; use MEASUREMENTS.md for actual logged allocations.
4. Render again with the exact same camera, exposure, resolution and samples. Compare the clean PNGs.
5. Show the protected character and mug; show a pottery Decimate modifier for the background-geometry example.
6. Demonstrate Restore Originals. Restore before changing camera/resolution or taking a closer shot of reduced background props.
7. Put the test configuration and 'scene-specific results' next to any public numerical claim.

## Suggested wording

**Keep the shot. Cut the waste.**

Protect the objects that matter. Let camera-aware texture and mesh budgets reduce the background overhead.

For numerical captions use 'In this Blender 5.3 / RTX 4060 Ti demo…' and the exact measurement label, rather than claiming every scene will behave the same.

## Provenance and rights

Geometry, procedural texture bakes and scripts were authored for this demo. No comic image is embedded or traced. The scene is inspired by the user-supplied burning-room concept; this delivery does not grant rights in an existing comic character, title or trademark. Review those rights before a meme-specific commercial campaign. You may redesign the original mascot or omit the optional familiar quote for your own branding.

Your original avocado project and the installed add-on were not edited. Raw logs and reproducible build/render scripts remain one folder above SHOWCASE. The native scene remains editable without the add-on; the add-on is needed for its protection UI and Restore operator.
'''
(OUT/'START_HERE.md').write_text(readme,encoding='utf-8')
print(json.dumps({'metrics':metrics,'core_preparation_seconds':core_overhead,'optimization_job_seconds':job_overhead,'quality':quality,'folder':str(OUT)},indent=2))
