"""Check unchanged lighting/camera/protected geometry and persistent full restoration."""
from pathlib import Path
import sys,json
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import vram_fixer
vram_fixer.register()

def state():
    s=bpy.context.scene
    objects={o.name:{'type':o.type,'matrix':[list(row) for row in o.matrix_world],
                     'modifiers':[(m.name,m.type,m.show_render,m.show_viewport) for m in o.modifiers],
                     'source_polygons':len(o.data.polygons) if o.type=='MESH' else None} for o in s.objects}
    lights={o.name:{'energy':o.data.energy,'color':list(o.data.color)} for o in s.objects if o.type=='LIGHT'}
    images={i.name:{'size':list(i.size),'colorspace':i.colorspace_settings.name} for i in bpy.data.images if i.type not in {'RENDER_RESULT','COMPOSITING'}}
    return {'objects':objects,'lights':lights,'images':images,
            'camera':s.camera.name,'resolution':[s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage],
            'samples':s.cycles.samples,'adaptive':s.cycles.use_adaptive_sampling,'threshold':s.cycles.adaptive_threshold,
            'seed':s.cycles.seed,'exposure':s.view_settings.exposure,'view_transform':s.view_settings.view_transform,
            'look':s.view_settings.look,'compositor':s.compositing_node_group.name}

bpy.ops.wm.open_mainfile(filepath=str(HERE/'burning_room_before.blend'))
before=state()
assert len(before['objects'])==656
bpy.ops.wm.open_mainfile(filepath=str(HERE/'burning_room_after.blend'))
after=state()
for field in ('lights','camera','resolution','samples','adaptive','threshold','seed','exposure','view_transform','look','compositor'):
    assert before[field]==after[field],field+' changed'
settings=bpy.context.scene.vram_fixer
assert settings.active_session
assert len(settings.image_changes)==10 and len(settings.mesh_changes)==22
protected=[item.object.name for item in settings.protected if item.object]
for name in protected:
    assert before['objects'][name]==after['objects'][name], 'Protected object changed: '+name
for name,original in before['objects'].items():
    current=after['objects'][name]
    assert original['matrix']==current['matrix'] and original['source_polygons']==current['source_polygons'],name+' source changed'
warnings=vram_fixer.operations.restore(bpy.context)
assert not warnings,warnings
restored=state()
assert restored==before,'Saved AFTER did not completely restore to BEFORE state'
result={'pass':True,'objects':656,'protected_objects_unchanged':len(protected),'textures_changed':10,'meshes_changed':22,
        'camera_lights_settings_equal':True,'source_meshes_unchanged':True,'saved_file_restore_matches_before':True}
(HERE/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('DEMO_VALIDATION_PASS',json.dumps(result))
