"""VRAM Fixer: camera-aware texture and mesh budgets for Cycles."""
bl_info = {
    'name': 'VRAM Fixer',
    'author': 'VRAM Fixer',
    'version': (1, 1, 1),
    'blender': (4, 2, 0),
    'location': 'View3D > Sidebar > VRAM Fixer',
    'description': 'Reference-sized camera analysis, protected assets and reversible VRAM optimization',
    'category': 'Render',
}

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       IntProperty, PointerProperty, StringProperty)
from . import analysis, operations


class VRF_Protected(bpy.types.PropertyGroup):
    object: PointerProperty(type=bpy.types.Object)


class VRF_NodeChange(bpy.types.PropertyGroup):
    material: PointerProperty(type=bpy.types.Material)
    tree: PointerProperty(type=bpy.types.NodeTree)
    node_name: StringProperty()
    token: StringProperty()


class VRF_ImageChange(bpy.types.PropertyGroup):
    original: PointerProperty(type=bpy.types.Image)
    optimized: PointerProperty(type=bpy.types.Image)
    nodes: CollectionProperty(type=VRF_NodeChange)


class VRF_MeshChange(bpy.types.PropertyGroup):
    object: PointerProperty(type=bpy.types.Object)
    modifier_name: StringProperty()
    uid: IntProperty()
    error_pixels: FloatProperty()
    samples: IntProperty()


class VRF_Settings(bpy.types.PropertyGroup):
    reference: PointerProperty(name='Size Reference', type=bpy.types.Object,
                              poll=lambda self, obj: obj.type == 'MESH',
                              description='Objects near this camera-space size are preserved; smaller ones get tighter budgets')
    protect_reference: BoolProperty(name='Protect Reference', default=True,
                                   description='Never modify the reference or any image it shares')
    protected: CollectionProperty(type=VRF_Protected)
    protected_index: IntProperty()
    textures: BoolProperty(name='Textures', default=True, description='Reduce safe UV image textures into reversible packed copies')
    meshes: BoolProperty(name='Meshes', default=True, description='Add non-applied Decimate modifiers to safe small dense meshes')
    preset: EnumProperty(name='Quality', items=[
        ('CAREFUL', 'Careful', '2x texel sampling; at least 35% geometry retention'),
        ('BALANCED', 'Balanced', '1.5x texel sampling; at least 16% geometry retention'),
        ('STRONG', 'Strong', '1.1x texel sampling; at least 8% geometry retention; test-render carefully')], default='CAREFUL')
    active_session: StringProperty(options={'HIDDEN'})
    image_changes: CollectionProperty(type=VRF_ImageChange)
    mesh_changes: CollectionProperty(type=VRF_MeshChange)
    status: StringProperty(default='Choose a reference, then Analyze or Fix VRAM.')
    estimated_mib: FloatProperty()


class VRF_OT_reference(bpy.types.Operator):
    bl_idname = 'vram_fixer.set_reference'
    bl_label = 'Use Active Object as Reference'
    bl_description = 'Use the active mesh to define medium/focus size in the render camera'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH' and not context.scene.vram_fixer.active_session

    def execute(self, context):
        context.scene.vram_fixer.reference = context.object
        return {'FINISHED'}


class VRF_OT_protect(bpy.types.Operator):
    bl_idname = 'vram_fixer.protect_selected'
    bl_label = 'Add Selected'
    bl_description = 'Protect selected objects and any images shared with them'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.vram_fixer
        if settings.active_session:
            self.report({'WARNING'}, 'Restore first to change exclusions')
            return {'CANCELLED'}
        existing = {x.object for x in settings.protected}
        for obj in context.selected_objects:
            if obj not in existing:
                settings.protected.add().object = obj
        return {'FINISHED'}


class VRF_OT_unprotect(bpy.types.Operator):
    bl_idname = 'vram_fixer.unprotect'
    bl_label = 'Remove'
    bl_description = 'Remove the highlighted exclusion; the object itself is not deleted'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.vram_fixer
        if not s.active_session and 0 <= s.protected_index < len(s.protected):
            s.protected.remove(s.protected_index)
            s.protected_index = max(0, min(s.protected_index, len(s.protected)-1))
        return {'FINISHED'}


class VRF_OT_analyze(bpy.types.Operator):
    bl_idname = 'vram_fixer.analyze'
    bl_label = 'Analyze'
    bl_description = 'Read-only preview; writes per-asset decisions and skip reasons to VRAM Fixer Report'

    def execute(self, context):
        context.window_manager.progress_begin(0, 1)
        try:
            plan = analysis.analyze(context)
            operations.write_report(plan)
            s = context.scene.vram_fixer
            s.estimated_mib = plan['saved'] / 1048576
            s.status = (f'{len(plan["images"])} textures / {len(plan["meshes"])} meshes | ~{s.estimated_mib:.1f} MiB textures'
                        if plan['images'] or plan['meshes'] else 'No reductions found. Open the report for skip reasons.')
            self.report({'INFO'} if plan['images'] or plan['meshes'] else {'WARNING'}, s.status)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        finally:
            context.window_manager.progress_end()


class VRF_OT_fix(bpy.types.Operator):
    bl_idname = 'vram_fixer.fix'
    bl_label = 'Fix VRAM'
    bl_description = 'Analyze current camera/frame and apply reversible optimizations; originals are preserved'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.window_manager.progress_begin(0, 1)
        try:
            # Always recompute: a preview is never trusted after scene edits.
            plan = analysis.analyze(context)
            textures, meshes = operations.apply(context, plan)
            operations.write_report(plan, applied=True)
            s = context.scene.vram_fixer
            s.estimated_mib = plan['saved'] / 1048576
            s.status = (f'Applied: {textures} textures / {meshes} meshes | ~{s.estimated_mib:.1f} MiB textures'
                        if textures or meshes else 'No changes applied. Open the report for skip reasons.')
            self.report({'INFO'} if textures or meshes else {'WARNING'}, s.status)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        finally:
            context.window_manager.progress_end()


class VRF_OT_restore(bpy.types.Operator):
    bl_idname = 'vram_fixer.restore'
    bl_label = 'Restore Originals'
    bl_description = 'Reconnect original images and remove only this session\'s Decimate modifiers'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            warnings = operations.restore(context)
            context.scene.vram_fixer.status = 'Originals restored.' if not warnings else 'Restored with warnings; see Info log.'
            for warning in warnings:
                self.report({'WARNING'}, warning)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class VRF_OT_report(bpy.types.Operator):
    bl_idname = 'vram_fixer.show_report'
    bl_label = 'Open Detailed Report'
    bl_description = 'Open the per-asset optimization report in a separate Text Editor window'

    def execute(self, context):
        text = bpy.data.texts.get('VRAM Fixer Report')
        if not text:
            self.report({'INFO'}, 'Run Analyze first')
            return {'CANCELLED'}
        bpy.ops.screen.info_log_show()
        window = context.window_manager.windows[-1]
        area = window.screen.areas[0]
        area.type = 'TEXT_EDITOR'
        area.spaces.active.text = text
        return {'FINISHED'}


class VRF_UL_protected(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.object.name if item.object else '(deleted object)', icon='LOCKED')


class VRF_PT_main(bpy.types.Panel):
    bl_label = 'VRAM Fixer'
    bl_idname = 'VRF_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VRAM Fixer'

    def draw(self, context):
        layout = self.layout
        s = context.scene.vram_fixer
        layout.label(text='CAMERA-AWARE / REVERSIBLE', icon='SHADING_RENDERED')
        if context.scene.render.engine != 'CYCLES':
            layout.label(text='Designed for Cycles', icon='INFO')
        if s.active_session:
            box = layout.box()
            box.label(text='Optimization active', icon='CHECKMARK')
            box.label(text='Restore before changing camera/frame.')
            box.label(text=f'{len(s.image_changes)} textures / {len(s.mesh_changes)} meshes')
            row = box.row()
            row.scale_y = 1.5
            row.operator('vram_fixer.restore', icon='LOOP_BACK')
        controls = layout.column()
        controls.enabled = not bool(s.active_session)
        box = controls.box()
        box.label(text='01  SIZE REFERENCE')
        box.prop(s, 'reference', text='')
        box.operator('vram_fixer.set_reference', icon='EYEDROPPER')
        box.prop(s, 'protect_reference')
        box = controls.box()
        box.label(text='02  NEVER TOUCH', icon='LOCKED')
        box.template_list('VRF_UL_protected', '', s, 'protected', s, 'protected_index', rows=3)
        row = box.row(align=True)
        row.operator('vram_fixer.protect_selected', icon='ADD')
        row.operator('vram_fixer.unprotect', icon='REMOVE')
        box = controls.box()
        box.label(text='03  OPTIMIZE')
        row = box.row(align=True)
        row.prop(s, 'textures', toggle=True, icon='IMAGE_DATA')
        row.prop(s, 'meshes', toggle=True, icon='MESH_DATA')
        box.prop(s, 'preset', text='')
        row = controls.row(align=True)
        row.scale_y = 1.6
        row.operator('vram_fixer.analyze', icon='VIEWZOOM')
        row.operator('vram_fixer.fix', icon='MOD_DECIM')
        layout.separator()
        for line in (s.status[i:i+42] for i in range(0, len(s.status), 42)):
            layout.label(text=line)
        layout.operator('vram_fixer.show_report', icon='TEXT')
        layout.label(text='Current camera + frame only.', icon='INFO')
        layout.label(text='Compare a test render before final output.')


CLASSES = (VRF_Protected, VRF_NodeChange, VRF_ImageChange, VRF_MeshChange, VRF_Settings,
           VRF_OT_reference, VRF_OT_protect, VRF_OT_unprotect, VRF_OT_analyze, VRF_OT_fix,
           VRF_OT_restore, VRF_OT_report, VRF_UL_protected, VRF_PT_main)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vram_fixer = PointerProperty(type=VRF_Settings)


def unregister():
    del bpy.types.Scene.vram_fixer
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
