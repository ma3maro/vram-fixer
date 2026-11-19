"""Build, preview, optimize and render the showcase in independent Blender processes."""
import sys
import argparse
import time
import json
import traceback
import runpy
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import vram_fixer
parser=argparse.ArgumentParser()
parser.add_argument('--action',choices=['build','preview','optimize','render','validate'],required=True)
parser.add_argument('--tag',required=True)
parser.add_argument('--input',default=str(HERE/'burning_room_before.blend'))
parser.add_argument('--percent',type=int,default=35)
parser.add_argument('--samples',type=int,default=32)
args,_=parser.parse_known_args(sys.argv[sys.argv.index('--')+1:])
result={'tag':args.tag,'action':args.action,'status':'started','blender':bpy.app.version_string}
start=time.perf_counter()

def checkpoint(stage,**fields):
    result.update(fields);result['stage']=stage
    (HERE/(args.tag+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('DEMO_STAGE',stage,json.dumps(fields),flush=True)

def devices(scene):
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.refresh_devices()
    enabled=[]
    for dev in prefs.devices:
        dev.use=dev.type=='OPTIX'
        if dev.use:enabled.append([dev.name,dev.type])
    if not enabled:raise RuntimeError('No OptiX GPU; CPU fallback forbidden for this comparison')
    scene.cycles.device='GPU'
    return enabled

def mesh_counts(scene):
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    counts={}
    for obj in scene.objects:
        if obj.type=='MESH' and not obj.hide_render:
            ev=obj.evaluated_get(deps)
            counts[obj.name]=sum(max(0,len(poly.vertices)-2) for poly in ev.data.polygons)
    return counts

try:
    if args.action=='build':
        runpy.run_path(str(HERE/'build_scene.py'),run_name='__main__')
        checkpoint('built',status='prepared',elapsed_seconds=time.perf_counter()-start)
    elif args.action=='validate':
        runpy.run_path(str(HERE/'validate_demo.py'),run_name='__main__')
        checkpoint('validated',status='validation_passed',elapsed_seconds=time.perf_counter()-start)
    else:
        vram_fixer.register();bpy.ops.wm.open_mainfile(filepath=str(Path(args.input).resolve()))
        scene=bpy.context.scene
        checkpoint('loaded',load_seconds=time.perf_counter()-start,devices=devices(scene))
        if args.action=='optimize':
            before=mesh_counts(scene)
            protected={p.object for p in scene.vram_fixer.protected if p.object}
            protected_modifiers={obj:[(m.name,m.type) for m in obj.modifiers] for obj in protected}
            t=time.perf_counter();plan=vram_fixer.analysis.analyze(bpy.context)
            (HERE/'optimization_plan.txt').write_text(plan['report'],encoding='utf-8')
            checkpoint('analyzed',analysis_seconds=time.perf_counter()-t,textures_planned=len(plan['images']),meshes_planned=len(plan['meshes']),estimated_texture_mib=plan['saved']/1048576)
            t=time.perf_counter();textures,meshes=vram_fixer.operations.apply(bpy.context,plan)
            after=mesh_counts(scene)
            for obj,mods in protected_modifiers.items():
                assert [(m.name,m.type) for m in obj.modifiers]==mods,'Protected object changed'
            vram_fixer.operations.write_report(plan,applied=True)
            (HERE/'optimization_applied.txt').write_text(plan['report'],encoding='utf-8')
            scene.render.filepath=str(HERE/'after.png')
            bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'burning_room_after.blend'),check_existing=False)
            checkpoint('saved_after',status='prepared',application_and_save_seconds=time.perf_counter()-t,
                       textures_changed=textures,meshes_changed=meshes,
                       measured_mesh_triangles_before=sum(before.values()),measured_mesh_triangles_after=sum(after.values()),
                       reduced_meshes=[{'name':name,'before':count,'after':after[name]} for name,count in before.items() if after.get(name,count)<count],
                       sampled_errors=[{'object':r.object.name,'error_px':r.error_pixels,'samples':r.samples} for r in scene.vram_fixer.mesh_changes])
        else:
            if args.action=='preview':
                scene.render.resolution_percentage=args.percent;scene.cycles.samples=args.samples
                scene.cycles.use_adaptive_sampling=False
            scene.render.filepath=str(HERE/(args.tag+'.png'))
            checkpoint('rendering',resolution=[scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage],
                       samples=scene.cycles.samples,adaptive=scene.cycles.use_adaptive_sampling,threshold=scene.cycles.adaptive_threshold,
                       seed=scene.cycles.seed,active_optimization=bool(scene.vram_fixer.active_session),
                       exposure=scene.view_settings.exposure,camera_matrix=[list(row) for row in scene.camera.matrix_world])
            t=time.perf_counter();render_result=bpy.ops.render.render(write_still=True)
            image=HERE/(args.tag+'.png')
            assert render_result=={'FINISHED'} and image.exists(),'Render failed'
            checkpoint('completed',status='render_completed',render_seconds=time.perf_counter()-t,output=str(image),elapsed_seconds=time.perf_counter()-start)
except Exception as exc:
    checkpoint('exception',status='exception',error=repr(exc),traceback=traceback.format_exc(),elapsed_seconds=time.perf_counter()-start)
    traceback.print_exc();sys.exit(2)
