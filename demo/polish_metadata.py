"""Only set sidebar status/help text; no render-affecting edits or product changes."""
from pathlib import Path
import sys,json
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import vram_fixer
vram_fixer.register()
opt=json.loads((HERE/'optimize_final.json').read_text(encoding='utf-8'))
for variant in ('before','after'):
    path=HERE/f'burning_room_{variant}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene=bpy.context.scene;s=scene.vram_fixer
    if variant=='before':
        assert not s.active_session
        s.status='Ready: torso reference. Mascot, cup, fire and smoke protected.'
    else:
        assert s.active_session and len(s.image_changes)==10 and len(s.mesh_changes)==22
        s.estimated_mib=opt['estimated_texture_mib']
        s.status=f'Applied: 10 textures / 22 meshes | ~{s.estimated_mib:.1f} MiB textures'
    bpy.ops.wm.save_as_mainfile(filepath=str(path),check_existing=False)
print('SIDEBAR_METADATA_READY')
