"""Build a native, editable burning-room miniature; no imported character/art assets."""
import bpy
import math
import random
import json
import sys
from pathlib import Path
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import vram_fixer

random.seed(17031)
bpy.ops.wm.read_factory_settings(use_empty=True)
vram_fixer.register()
scene = bpy.context.scene
scene.name = 'KEEP THE SHOT | Burning Room'
COL = {}
for name in ['00 | ROOM', '01 | MASCOT - PROTECTED', '02 | CHAIR AND TABLE',
             '03 | COFFEE - PROTECTED', '04 | SHELVES AND DETAILS', '05 | FIRE - PROTECTED',
             '06 | SMOKE AND EMBERS - PROTECTED', '07 | LIGHTS AND CAMERA', '08 | OPTIONAL SPEECH']:
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    COL[name[:2]] = col


def srgb(text):
    text = text.lstrip('#')
    values = [int(text[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values) + (1,)


def put(obj, name, group='04'):
    obj.name = name
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    COL[group].objects.link(obj)
    return obj


def solid(name, color, rough=.5, metal=0, subsurface=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = srgb(color)
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = srgb(color)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Subsurface Weight'].default_value = subsurface
    return mat


def bump(mat, scale=80, strength=.2, distance=.012):
    nt = mat.node_tree
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 3
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = distance
    nt.links.new(noise.outputs['Fac'], b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], nt.nodes.get('Principled BSDF').inputs['Normal'])


TEX = {}
for recipe in json.loads((HERE/'texture_manifest.json').read_text(encoding='utf-8')):
    tree = bpy.data.node_groups.new('BAKED SURFACE | ' + recipe['name'], 'ShaderNodeTree')
    tree.interface.new_socket(name='Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    tree.interface.new_socket(name='Roughness', in_out='OUTPUT', socket_type='NodeSocketFloat')
    output = tree.nodes.new('NodeGroupOutput')
    for channel, key in [('Color', 'base'), ('Roughness', 'rough')]:
        image = bpy.data.images.load(recipe[key], check_existing=True)
        image.name = recipe['name'] + (' | COLOR' if key=='base' else ' | ROUGHNESS')
        if key == 'rough':
            image.colorspace_settings.name = 'Non-Color'
        image.pack()
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        node.label = f'{recipe["edge"]}px source bake - intentionally oversized demo asset'
        node.location = (-250, 0 if key=='base' else -240)
        tree.links.new(node.outputs['Color'], output.inputs[channel])
    TEX[recipe['name']] = tree


def textured(name, family, tint='#FFFFFF'):
    mat = solid(name, tint, .65)
    preview_colors = {'green_plaster':'#657753','floor_oak':'#6E4427','table_oak':'#9C683B','shelf_walnut':'#583521','chair_weave':'#9B4227','book_leather':'#957751','aged_paper':'#C9B78B'}
    base_preview = srgb(preview_colors[family]); tint_preview = srgb(tint)
    mat.diffuse_color = tuple(base_preview[i]*tint_preview[i] for i in range(3)) + (1,)
    nt = mat.node_tree
    group = nt.nodes.new('ShaderNodeGroup')
    group.node_tree = TEX[family]
    group.location = (-600, 80)
    mix = nt.nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 1
    mix.inputs[2].default_value = srgb(tint)
    mix.location = (-300, 100)
    nt.links.new(group.outputs['Color'], mix.inputs[1])
    nt.links.new(mix.outputs[0], nt.nodes.get('Principled BSDF').inputs['Base Color'])
    nt.links.new(group.outputs['Roughness'], nt.nodes.get('Principled BSDF').inputs['Roughness'])
    bump(mat, 100 if family!='green_plaster' else 44, .18, .009)
    return mat


wall = textured('ROOM | fire-aged sage plaster', 'green_plaster')
floor = textured('ROOM | smoky oak floorboards', 'floor_oak')
tablemat = textured('TABLE | endgrain and oak', 'table_oak')
walnut = textured('DETAIL | walnut grain', 'shelf_walnut')
fabric = textured('CHAIR | woven rust upholstery', 'chair_weave')
paper = textured('BOOKS | foxed paper', 'aged_paper')
bookmats = [textured('BOOK | '+name, 'book_leather', color) for name, color in [
    ('oxblood','#8F4943'),('petrol','#3F7773'),('ochre','#C8A35D'),('moss','#71905B'),
    ('cream','#F2D9AF'),('ink','#546377')]]
trim = solid('ROOM | deep green enamel','#253E36', .53)
char = solid('FIRE | charred timber','#17120F', .92)
bump(char, 24, .7, .055)
black = solid('DETAIL | warm charcoal','#171715', .55)
bronze = solid('DETAIL | aged warm brass','#A7793C', .33, .78)
ash = solid('FIRE | ash edges','#5E5B53', .98)
ivory = solid('HERO | ivory ceramic','#EEE4C9', .23)
coat = solid('HERO | cinnamon felt fur','#C18A42', .83, subsurface=.035)
bump(coat, 145, .22, .009)
cream = solid('HERO | warm cream chest','#E4C48A', .86, subsurface=.035)
bump(cream, 135, .2, .008)
ear = solid('HERO | velvet brown ears','#4E3022', .9)
bump(ear, 95, .3, .013)
nose = solid('HERO | leather nose','#211B17', .24)
bump(nose, 120, .25, .005)
eye_white = solid('HERO | warm eye whites','#F5ECD9', .22)
eye_dark = solid('HERO | dark amber eyes','#271A12', .1)
hatmat = solid('HERO | camel felt fedora','#A86D2D', .85)
bump(hatmat, 155, .18, .008)
ribbon = solid('HERO | charcoal hat ribbon','#25251E', .75)
ceramics = [solid('POTTERY | '+n,c,.25) for n,c in [('teal','#2F6E66'),('ivory','#DDD0AA'),('terracotta','#A65E3E')]]


def box(name, location, dimensions, material, bevel=.02, group='04'):
    x,y,z = [d/2 for d in dimensions]
    vertices = [(-x,-y,-z),(-x,-y,z),(-x,y,-z),(-x,y,z),(x,-y,-z),(x,-y,z),(x,y,-z),(x,y,z)]
    faces = [(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]
    mesh = bpy.data.meshes.new(name+' mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.uv_layers.new(name='Surface UV')
    for poly in mesh.polygons:
        for loop, uv in zip(poly.loop_indices, [(0,0),(0,1),(1,1),(1,0)]):
            mesh.uv_layers.active.data[loop].uv = uv
    obj = bpy.data.objects.new(name, mesh)
    COL[group].objects.link(obj)
    obj.location = location
    obj.data.materials.append(material)
    if bevel:
        m = obj.modifiers.new('Soft manufactured edges', 'BEVEL')
        m.width = bevel
        m.segments = 3
        m = obj.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
        m.keep_sharp = True
    return obj


def sphere(name, location, scale, material, group='04', segments=48, rings=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1, location=location)
    obj = put(bpy.context.object, name, group)
    obj.scale = scale
    obj.data.materials.append(material)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def cylinder(name, location, radius, depth, material, group='04', vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = put(bpy.context.object, name, group)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new('Rounded edges', 'BEVEL')
    bevel.width = min(.025, depth/5)
    bevel.segments = 3
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def curve(name, points, radius, material, group='04', cyclic=False, resolution=3):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 12
    data.bevel_depth = radius
    data.bevel_resolution = resolution
    spline = data.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for p, co in zip(spline.bezier_points, points):
        p.co = co
        p.handle_left_type = p.handle_right_type = 'AUTO'
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    COL[group].objects.link(obj)
    data.materials.append(material)
    return obj


def rod(name, a, b, radius, material, group='04'):
    a,b = Vector(a),Vector(b)
    obj = cylinder(name, (a+b)/2, radius, (b-a).length, material, group, 32)
    obj.rotation_euler = (b-a).to_track_quat('Z','Y').to_euler()
    return obj


def lathe(name, profile, location, material, group='04', sides=96):
    verts=[]; faces=[]
    for radius,z in profile:
        verts.extend((radius*math.cos(i/sides*math.tau), radius*math.sin(i/sides*math.tau), z) for i in range(sides))
    for row in range(len(profile)-1):
        for i in range(sides):
            j=(i+1)%sides
            faces.append((row*sides+i,row*sides+j,(row+1)*sides+j,(row+1)*sides+i))
    mesh=bpy.data.meshes.new(name+' mesh');mesh.from_pydata(verts,[],faces)
    mesh.uv_layers.new(name='Surface UV')
    for index,p in enumerate(mesh.polygons):
        row,i=divmod(index,sides)
        for loop,uv in zip(p.loop_indices,[(i/sides,row/(len(profile)-1)),((i+1)/sides,row/(len(profile)-1)),((i+1)/sides,(row+1)/(len(profile)-1)),(i/sides,(row+1)/(len(profile)-1))]):
            mesh.uv_layers.active.data[loop].uv=uv
        p.use_smooth=True
    obj=bpy.data.objects.new(name,mesh);COL[group].objects.link(obj);obj.location=location;mesh.materials.append(material)
    return obj


def text(name, body, location, size, material, group='04'):
    data=bpy.data.curves.new(name,'FONT');data.body=body;data.align_x='CENTER';data.align_y='CENTER'
    data.size=size;data.space_line=1.35;data.extrude=.001;data.bevel_depth=.0008
    obj=bpy.data.objects.new(name,data);COL[group].objects.link(obj);obj.location=location
    obj.rotation_euler=(math.pi/2,0,0);data.materials.append(material)
    return obj


# Set construction: actual floorboards, paneled walls, furniture, framing.
box('ROOM | miniature foundation',(0,0,-.2),(10.5,7.4,.4),char,.10,'00')
for row in range(13):
    y=-3.3+row*.54
    x=-5.12
    while x<5.1:
        length=min(random.uniform(1.75,3.1),5.12-x)
        if length<.05:break
        box('FLOOR | individual scorched oak board',(x+length/2,y,.015),(length-.018,.525,.075),floor,.012,'00')
        x+=length
box('ROOM | back plaster wall',(0,3.6,2.43),(10.5,.22,4.85),wall,.04,'00')
box('ROOM | left plaster return',(-5.15,.20,2.43),(.22,7,4.85),wall,.04,'00')
box('ROOM | short right return',(5.15,2.55,2.43),(.22,2.1,4.85),wall,.04,'00')
for z,height in [(.12,.16),(.86,.13),(.96,.04)]:
    box('ROOM | back painted rail',(0,3.42,z),(10.3,.11,height),trim,.015,'00')
    box('ROOM | left painted rail',(-4.99,.1,z),(.12,6.7,height),trim,.015,'00')
for x in [i*.69-4.8 for i in range(15)]:
    box('ROOM | back wainscot stile',(x,3.43,.49),(.065,.09,.67),trim,.01,'00')
# Window: luminous exterior with real wooden mullions and folded curtains.
windowmat=solid('ROOM | moonlit window','#548D9F',.6)
bs=windowmat.node_tree.nodes.get('Principled BSDF');bs.inputs['Emission Color'].default_value=srgb('#67A6BE');bs.inputs['Emission Strength'].default_value=.7
box('WINDOW | blue night beyond',(-3.52,3.455,2.85),(1.65,.055,2.25),windowmat,.01,'00')
for x in (-4.41,-2.63,-3.52):
    box('WINDOW | charred upright',(x,3.32,2.85),(.09,.18,2.45),walnut,.02,'00')
for z in (1.63,2.85,4.07):
    box('WINDOW | cross frame',(-3.52,3.32,z),(1.88,.18,.10),walnut,.018,'00')
box('WINDOW | deep sill',(-3.52,3.18,1.61),(2.1,.46,.12),walnut,.025,'00')
for side in (-1,1):
    verts=[];faces=[];nx=24;nz=30
    for j in range(nz):
        t=j/(nz-1)
        for i in range(nx):
            u=i/(nx-1)
            x=-3.52+side*(.73+.3*u+.08*math.sin(t*math.pi))
            verts.append((x,3.19-.075*math.sin(u*math.pi*7),4.11-t*2.30+.025*math.sin(u*21)))
    for j in range(nz-1):
        for i in range(nx-1):a=j*nx+i;faces.append((a,a+1,a+1+nx,a+nx))
    mesh=bpy.data.meshes.new('Curtain folds');mesh.from_pydata(verts,[],faces);mesh.uv_layers.new()
    for p in mesh.polygons:
        p.use_smooth=True
        for loop in p.loop_indices:
            idx=mesh.loops[loop].vertex_index;mesh.uv_layers.active.data[loop].uv=(idx%nx/(nx-1),idx//nx/(nz-1))
    obj=bpy.data.objects.new('WINDOW | hanging woven curtain',mesh);COL['00'].objects.link(obj);mesh.materials.append(fabric)
    m=obj.modifiers.new('Fabric thickness','SOLIDIFY');m.thickness=.012
# Back-wall art, tiny placard and cabinet.
box('ART | scorched picture frame',(-.15,3.35,3.08),(1.5,.15,1.14),walnut,.035,'04')
box('ART | matte illustration backing',(-.15,3.25,3.08),(1.31,.035,.96),trim,.01,'04')
text('ART | calm print','TAKE A\nBREATH.',(-.15,3.218,3.08),.18,ivory)
box('ART | sign frame',(2.05,3.37,3.68),(1.1,.10,.36),char,.02,'04')
text('ART | ironic safety sign','NO SMOKING',(2.05,3.304,3.68),.105,ivory)
box('CABINET | body',(-3.55,2.60,.64),(2.2,.95,1.15),walnut,.05,'04')
box('CABINET | top',(-3.55,2.57,1.25),(2.35,1.06,.12),tablemat,.035,'04')
for z in (.34,.67,1.0):
    box('CABINET | drawer face',(-3.55,2.105,z),(2.02,.11,.26),walnut,.02,'04')
    for x in (-4.12,-2.98):
        sphere('CABINET | brass pull',(x,2.02,z),(.045,.033,.045),bronze)
# Main table: planar UV top, chunky beveled lip, turned legs.
tx,ty=1.35,-.32
cylinder('TABLE | solid oak tabletop',(tx,ty,1.35),1.13,.16,tablemat,'02',128)
# Proper planar UV on top face avoids an atlas wasting resolution.
obj=bpy.data.objects['TABLE | solid oak tabletop']
for p in obj.data.polygons:
    if abs(p.normal.z)>.9:
        for loop in p.loop_indices:
            co=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            obj.data.uv_layers.active.data[loop].uv=(co.x/2.26+.5,co.y/2.26+.5)
for a in [math.pi/4+i*math.pi/2 for i in range(4)]:
    x=tx+math.cos(a)*.72;y=ty+math.sin(a)*.72
    profile=[(.07,0),(.10,.06),(.07,.18),(.055,.33),(.09,.47),(.07,.6),(.065,1.25)]
    lathe('TABLE | turned oak leg',profile,(x,y,.05),walnut,'02',48)
    sphere('TABLE | dark brass foot',(x,y,.075),(.085,.085,.035),bronze,'02')
# Chair upholstery and carpentry.
cx,cy=-1.18,.35
box('CHAIR | seat frame',(cx,cy,.94),(1.10,.94,.14),walnut,.05,'02')
box('CHAIR | rounded woven cushion',(cx,cy-.03,1.045),(1.04,.89,.19),fabric,.085,'02')
box('CHAIR | upholstered back',(cx,cy+.49,1.77),(1.08,.21,1.42),fabric,.10,'02')
for x in (cx-.48,cx+.48):
    for y in (cy-.35,cy+.37):
        rod('CHAIR | wooden leg',(x+(.06 if x>cx else -.06),y,.07),(x,y,1.02),.065,walnut,'02')
    rod('CHAIR | back post',(x,cy+.46,.85),(x,cy+.5,2.53),.055,walnut,'02')
    sphere('CHAIR | brass finial',(x,cy+.5,2.52),(.065,.065,.065),bronze,'02')
for x in (cx-.28,cx+.28):
    for z in (1.65,2.10):
        sphere('CHAIR | upholstery button',(x,cy+.355,z),(.035,.018,.035),bronze,'02',24,16)
# Original stylized mascot, seated and deliberately unconcerned.
ox,oy=cx,cy-.04
body=sphere('MASCOT | Torso - SIZE REFERENCE',(ox,oy,1.74),(.48,.35,.68),coat,'01',96,64)
sphere('MASCOT | rounded hips',(ox,oy-.02,1.20),(.46,.34,.27),coat,'01',64,48)
sphere('MASCOT | cream chest',(ox,oy-.316,1.72),(.32,.09,.48),cream,'01',64,48)
head=sphere('MASCOT | head',(ox,oy-.015,2.71),(.61,.47,.60),coat,'01',96,64)
for side in (-1,1):
    e=sphere('MASCOT | drooping velvet ear',(ox+side*.575,oy+.045,2.56),(.175,.205,.49),ear,'01',64,48)
    e.rotation_euler[1]=side*-.17
    sphere('MASCOT | haunch',(ox+side*.30,oy-.05,1.19),(.24,.28,.26),coat,'01')
    leg=sphere('MASCOT | dangling leg',(ox+side*.28,oy-.25,.84),(.15,.18,.31),coat,'01')
    sphere('MASCOT | soft paw',(ox+side*.28,oy-.40,.595),(.19,.27,.13),coat,'01')
    for k in (-1,0,1):
        curve('MASCOT | tiny toe seam',[(ox+side*.28+k*.055,oy-.635,.60),(ox+side*.28+k*.055,oy-.58,.64)],.004,ear,'01',resolution=2)
    curve('MASCOT | relaxed arm',[(ox+side*.39,oy-.05,2.08),(ox+side*.45,oy-.30,1.66),(ox+side*.24,oy-.42,1.37)],.115,coat,'01',resolution=5)
    sphere('MASCOT | resting hand',(ox+side*.21,oy-.43,1.35),(.18,.12,.105),coat,'01')
    # The eye objects project beyond the felt head; pupils glance toward the cup.
    x=ox+side*.245
    sphere('MASCOT | porcelain eye',(x,oy-.426,2.83),(.18,.105,.215),eye_white,'01',64,48)
    sphere('MASCOT | amber pupil',(x+.035,oy-.512,2.825),(.098,.039,.139),eye_dark,'01',64,48)
    sphere('MASCOT | eye catchlight',(x+.007,oy-.547,2.88),(.022,.012,.027),ivory,'01',24,16)
    sphere('MASCOT | soft half-closed upper lid',(x,oy-.45,3.005),(.188,.123,.12),coat,'01',64,40)
    curve('MASCOT | relaxed upper eyelid',[(x-.16,oy-.46,2.92),(x,oy-.56,2.90),(x+.16,oy-.45,2.94)],.016,coat,'01')
    curve('MASCOT | brow',[(x-.10,oy-.375,3.12),(x+.02,oy-.405,3.14),(x+.12,oy-.37,3.10)],.023,ear,'01')
sphere('MASCOT | cream muzzle',(ox+.075,oy-.40,2.46),(.36,.29,.205),cream,'01',64,48)
sphere('MASCOT | velvet nose',(ox+.15,oy-.663,2.49),(.155,.105,.105),nose,'01',64,40)
curve('MASCOT | quiet smile',[(ox+.15,oy-.653,2.435),(ox+.10,oy-.662,2.35),(ox+.26,oy-.605,2.32),(ox+.34,oy-.537,2.37)],.012,ear,'01')
# Felt hat: native lathed crown, brim, ribbon, slightly tilted as one assembly.
hatroot=bpy.data.objects.new('MASCOT | fedora assembly',None);COL['01'].objects.link(hatroot)
hatroot.location=(ox,oy+.015,3.22);hatroot.rotation_euler=(.07,-.12,-.10)
for name,profile,material in [
    ('brim',[(0,.015),(.36,0),(.60,-.015),(.66,.015),(.62,.045),(.38,.055),(0,.06)],hatmat),
    ('crown',[(.40,.035),(.405,.12),(.37,.35),(.32,.46),(.23,.47),(.12,.41),(0,.43)],hatmat),
    ('ribbon',[(.402,.10),(.40,.13),(.391,.20),(.387,.23)],ribbon)]:
    obj=lathe('MASCOT | fedora '+name,profile,(0,0,0),material,'01',112);obj.scale.y=.82;obj.parent=hatroot
# Fine three-dimensional felt nap, not an image overlay.
def felt(name,center,radii,count,material,skip_face=False):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.bevel_depth=.0014;data.bevel_resolution=0;data.resolution_u=1
    center=Vector(center)
    for _ in range(count):
        z=random.uniform(-1,1);angle=random.random()*math.tau;q=math.sqrt(1-z*z)
        n=Vector((q*math.cos(angle),q*math.sin(angle),z))
        if skip_face and n.y<-.44:continue
        point=center+Vector((n.x*radii[0],n.y*radii[1],n.z*radii[2]))
        length=random.uniform(.009,.020)
        strand=data.splines.new('POLY');strand.points.add(2)
        for p,t in zip(strand.points,(0,.5,1)):
            co=point+n*length*t+Vector((.003*math.sin(angle)*t,0,-.002*t*t))
            p.co=(*co,1);p.radius=1-t*.90
    obj=bpy.data.objects.new(name,data);COL['01'].objects.link(obj);data.materials.append(material)
felt('MASCOT | head felt nap',(ox,oy-.015,2.71),(.611,.471,.601),6500,coat,True)
felt('MASCOT | torso felt nap',(ox,oy,1.74),(.481,.351,.681),6500,coat,True)
# Open, thick-walled ceramic cup and real coffee/handle.
mx,my=tx+.12,ty-.36;mz=1.435
profile=[(.0,0),(.17,0),(.19,.025),(.205,.07),(.236,.43),(.24,.48),(.232,.493),(.211,.48),(.208,.44),(.181,.09),(.155,.055),(0,.055)]
lathe('COFFEE | hand-thrown cup',profile,(mx,my,mz),ivory,'03',112)
curve('COFFEE | ceramic handle',[(mx+.216,my,mz+.39),(mx+.40,my,mz+.38),(mx+.42,my,mz+.21),(mx+.23,my,mz+.14)],.046,ivory,'03',resolution=5)
coffee=solid('COFFEE | espresso','#25130A',.13)
cylinder('COFFEE | dark surface',(mx,my,mz+.425),.206,.012,coffee,'03',96)
latte=solid('COFFEE | crema','#C99C58',.52)
curve('COFFEE | crema spiral',[(mx+(.01+i*.0018)*math.cos(i*.30),my+(.01+i*.0018)*math.sin(i*.30),mz+.433) for i in range(80)],.005,latte,'03',resolution=2)
text('COFFEE | embossed word','FINE.',(mx,my-.237,mz+.255),.083,trim,'03')
for _ in range(26):
    a=random.random()*math.tau;r=.192*math.sqrt(random.random())
    sphere('COFFEE | crema bubble',(mx+r*math.cos(a),my+r*math.sin(a),mz+.433),(.004,.004,.0015),latte,'03',12,8)
# Steam strands are quiet translucent geometry, not a flat sprite.
steam=solid('COFFEE | steam','#BFC5BD',.8)
nt=steam.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');transparent=nt.nodes.new('ShaderNodeBsdfTransparent');em=nt.nodes.new('ShaderNodeEmission');em.inputs['Color'].default_value=(.35,.40,.36,1);em.inputs['Strength'].default_value=.16
mix=nt.nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.18;nt.links.new(transparent.outputs[0],mix.inputs[1]);nt.links.new(em.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs['Surface'])
for k in range(3):
    pts=[(mx+(k-1)*.07+.025*math.sin(t*8+k),my+.025*math.cos(t*6+k),mz+.45+t*.43) for t in [i/7 for i in range(8)]]
    curve('COFFEE | delicate steam',pts,.005,steam,'03',resolution=2)
# Bookshelf with real books, visible texture sampling and detailed small vessels.
shx,shy=3.65,2.78
for x in (shx-.89,shx+.89):box('SHELF | upright',(x,shy,1.63),(.12,.65,3.20),walnut,.025)
box('SHELF | dark backing',(shx,shy+.28,1.63),(1.8,.08,3.20),walnut,.015)
for z in (.12,.89,1.68,2.47,3.22):box('SHELF | shelf board',(shx,shy-.025,z),(1.88,.72,.12),walnut,.025)
for shelf_z in (.20,.97,1.76):
    x=shx-.77
    for i in range(8):
        width=random.uniform(.105,.18);height=random.uniform(.39,.60);depth=random.uniform(.33,.43)
        x+=width/2
        mat=random.choice(bookmats)
        box('BOOK | page block',(x,shy-.04,shelf_z+height/2),(width-.025,depth-.035,height-.035),paper,.008)
        for side in (-1,1):box('BOOK | leather cover',(x+side*width/2,shy-.04,shelf_z+height/2),(.018,depth+.015,height+.018),mat,.006)
        box('BOOK | curved spine',(x,shy-depth/2-.04,shelf_z+height/2),(width,.035,height),mat,.012)
        for dz in (-height*.31,height*.31):box('BOOK | gilt spine band',(x,shy-depth/2-.060,shelf_z+height/2+dz),(width*.85,.008,.012),bronze,.002)
        x+=width/2+.025
# Dense, small real geometry: these are meaningful Decimate candidates.
for i,(x,y,z) in enumerate([(2.99,2.73,2.55),(3.58,2.73,2.55),(4.18,2.75,2.55),(-4.05,2.60,1.32),(-3.38,2.60,1.32),(-2.83,2.60,1.32)]):
    h=random.uniform(.37,.61);radius=random.uniform(.12,.20)
    profile=[]
    for j in range(129):
        t=j/128
        r=radius*(.52+.48*math.sin(math.pi*t)**.65)*(1-.35*t)+.012*math.sin(t*math.pi*9)
        profile.append((r,h*t))
    profile += [(radius*.34,h),(radius*.32,h-.018)]
    lathe('DECIMATE CANDIDATE | fluted pottery '+str(i+1),profile,(x,y,z),ceramics[i%3],sides=192)
# Stacked books and loose cards on cabinet.
for i in range(3):
    book=box('BOOK | stacked journal',(-3.85,2.49,1.36+i*.095),(.62,.43,.085),random.choice(bookmats),.012)
    book.rotation_euler[2]=random.uniform(-.15,.15)
for i in range(6):
    card=box('DETAIL | loose foxed page',(random.uniform(-2.8,2.8),random.uniform(-2.5,1.8),.073),(.26,.18,.004),paper,.002)
    card.rotation_euler[2]=random.random()*math.tau
# Charred roof structure and scattered fallen wood.
for y in (-.5,1.35,3.13):box('FIRE | charred ceiling beam',(0,y,4.65),(10.35,.18,.22),char,.035,'00')
for x in (-4.88,4.88):box('FIRE | vertical charred support',(x,3.36,2.37),(.23,.26,4.72),char,.035,'00')
for i in range(52):
    x=random.choice([-1,1])*random.uniform(2.3,4.7);y=random.uniform(-2.8,2.7)
    piece=box('FIRE | broken charcoal',(x,y,.095),(random.uniform(.08,.32),random.uniform(.03,.07),random.uniform(.04,.10)),char,.012,'00')
    piece.rotation_euler[2]=random.random()*math.tau
for _ in range(13):
    x=random.uniform(-4.8,4.8);z=random.uniform(1.15,4.25)
    if abs(x+3.52)<1.2:continue
    pts=[(x,3.468,z)]
    for j in range(4):pts.append((pts[-1][0]+random.uniform(-.12,.12),3.468,pts[-1][2]+random.uniform(.07,.20)))
    curve('ROOM | plaster crack',pts,.0055,char,'00',resolution=1)
# A floor-standing brass lamp, slightly forlorn.
lathe('DETAIL | lamp weighted base',[(0,0),(.25,0),(.28,.035),(.22,.075),(.12,.10),(0,.10)],(-3.18,1.42,.07),bronze,sides=80)
rod('DETAIL | lamp standard',(-3.18,1.42,.15),(-3.18,1.42,2.62),.027,bronze)
lathe('DETAIL | lamp shade',[(.40,0),(.43,.025),(.26,.55),(.23,.57),(.215,.55),(.40,.025)],(-3.18,1.42,2.49),ivory,sides=96)
# Three-dimensional sculpted fire, with translucent wisps and a hot core.
def fire_material(name,core=False):
    mat=bpy.data.materials.new(name);mat.use_nodes=True;nt=mat.node_tree;nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission')
    coords=nt.nodes.new('ShaderNodeTexCoord');sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(coords.outputs['Generated'],sep.inputs[0])
    ramp=nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
    for i,(p,col) in enumerate([(0,'#FF5005'),(.22,'#FFA820'),(.57,'#FF6508'),(.88,'#D51B02'),(1,'#4B0701')]):
        e=ramp.color_ramp.elements[0] if i==0 else ramp.color_ramp.elements.new(p);e.position=p;e.color=srgb(col)
    nt.links.new(sep.outputs['Z'],ramp.inputs['Fac']);nt.links.new(ramp.outputs['Color'],em.inputs['Color'])
    em.inputs['Strength'].default_value=3.0 if core else 1.4
    noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=4.5;noise.inputs['Detail'].default_value=3;noise.inputs['Roughness'].default_value=.72
    nt.links.new(coords.outputs['Generated'],noise.inputs['Vector'])
    mask=nt.nodes.new('ShaderNodeValToRGB');mask.color_ramp.elements[0].position=.23;mask.color_ramp.elements[0].color=(.05,.05,.05,1);mask.color_ramp.elements[1].position=.70
    nt.links.new(noise.outputs['Fac'],mask.inputs[0])
    trans=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');nt.links.new(mask.outputs['Color'],mix.inputs[0]);nt.links.new(trans.outputs[0],mix.inputs[1]);nt.links.new(em.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs['Surface'])
    return mat
flame_outer=fire_material('FIRE | orange translucent tongues')
flame_core=fire_material('FIRE | golden core',True)

def flame(name,location,height,radius,seed,material):
    rng=random.Random(seed);ph=rng.random()*6.28;verts=[];faces=[];rows=30;sides=20
    lean=rng.uniform(-.30,.30)
    for j in range(rows):
        t=j/(rows-1)
        r=max(.001,radius*(math.sin(math.pi*(t*.95+.03))**.7)*(1-t)**.30)
        dx=lean*height*.55*t*t+.20*math.sin(t*9+ph)*math.sin(t*math.pi);dy=.13*math.cos(t*10+ph)*t
        for i in range(sides):
            a=i/sides*math.tau
            ripple=1+.12*math.sin(a*3+t*12+ph)+.07*math.cos(a*5-t*17)
            verts.append((dx+r*ripple*math.cos(a),dy+r*ripple*.52*math.sin(a),height*t))
    for j in range(rows-1):
        for i in range(sides):a=j*sides+i;b=j*sides+(i+1)%sides;faces.append((a,b,b+sides,a+sides))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces)
    for p in mesh.polygons:p.use_smooth=True
    obj=bpy.data.objects.new(name,mesh);COL['05'].objects.link(obj);obj.location=location;mesh.materials.append(material)
    return obj
# Deliberate framing: never put opaque flames over the face or coffee.
clusters=[(-4.50,-1.55,2.8,.44),(-3.80,-2.65,1.7,.36),(-4.5,1.9,3.35,.48),
          (-2.5,2.95,2.05,.26),(.95,3.1,2.70,.34),(2.65,2.55,2.95,.40),
          (4.55,.75,3.30,.48),(4.05,-1.15,2.05,.38),(3.10,-2.55,1.40,.35),
          (-.2,3.2,1.50,.20),(4.5,2.75,2.8,.38)]
for index,(x,y,h,r) in enumerate(clusters):
    for j in range(3):
        xx=x+(j-1)*r*.58;yy=y+random.uniform(-.12,.12);hh=h*random.uniform(.65,1.05)
        flame('FIRE | outer tongue', (xx,yy,.07),hh,r*1.03,index*19+j,flame_outer)
        flame('FIRE | hot inner tongue',(xx,yy-.025,.08),hh*.65,r*.28,index*19+j+120,flame_core)
    sphere('FIRE | floor scorch',(x,y,.058),(r*1.4,r*.9,.004),char,'00',32,16)
# Layered volume smoke under the ceiling; dark edges, no flat billboards.
smoke=bpy.data.materials.new('SMOKE | billowing absorption');smoke.use_nodes=True;nt=smoke.node_tree;nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputMaterial');vol=nt.nodes.new('ShaderNodeVolumePrincipled');vol.inputs['Color'].default_value=srgb('#423E38');vol.inputs['Anisotropy'].default_value=.18
noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3.0;noise.inputs['Detail'].default_value=3.5
ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.27;ramp.color_ramp.elements[0].color=(0,0,0,1);ramp.color_ramp.elements[1].position=.73;ramp.color_ramp.elements[1].color=(1.10,1.10,1.10,1)
nt.links.new(noise.outputs['Fac'],ramp.inputs[0]);nt.links.new(ramp.outputs['Color'],vol.inputs['Density']);nt.links.new(vol.outputs[0],out.inputs['Volume'])
for i in range(21):
    x=-5+i*.50;y=random.uniform(.4,2.9);z=random.uniform(4.05,4.55)
    sphere('SMOKE | overhead billow',(x,y,z),(random.uniform(.55,.85),random.uniform(.6,1.0),random.uniform(.36,.60)),smoke,'06',24,16)
for x,y in [(-4.5,1.9),(4.5,.7),(2.8,2.6)]:
    for j in range(4):sphere('SMOKE | rising plume',(x+.11*j,y+.12*j,2.5+j*.42),(.30+j*.05,.30+j*.04,.45),smoke,'06',20,12)
ember=bpy.data.materials.new('FIRE | glowing ember');ember.use_nodes=True;en=ember.node_tree.nodes.get('Principled BSDF');en.inputs['Base Color'].default_value=srgb('#E76B15');en.inputs['Emission Color'].default_value=srgb('#FF8B22');en.inputs['Emission Strength'].default_value=5
for i in range(95):
    x=random.uniform(-4.7,4.7);y=random.uniform(-1.8,3.1);z=random.uniform(.3,4.35)
    if abs(x-ox)<.75 and y<1.0 and z>1.3:continue
    obj=sphere('EMBER | floating cinder',(x,y,z),(random.uniform(.004,.013),.005,random.uniform(.009,.029)),ember,'06',8,6)
    obj.rotation_euler[1]=random.uniform(-.4,.4)
# Optional editable quote is kept out of clean renders.
speech=sphere('OPTIONAL | speech balloon',(1.05,.68,3.60),(1.04,.10,.44),ivory,'08',64,40)
text('OPTIONAL | editable quote','THIS IS\nFINE.',(1.05,.562,3.60),.22,black,'08')
COL['08'].hide_render=True;COL['08'].hide_viewport=True
# Light deliberately: warm practicals/fire with a cool window counter-light.
def area(name,location,target,power,color,size):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.color=srgb(color)[:3];data.shape='DISK';data.size=size
    obj=bpy.data.objects.new(name,data);COL['07'].objects.link(obj);obj.location=location;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler();return obj
area('LIGHT | broad fire key',(-3,-3.5,4.4),(-1,0,2),850,'#FFD19A',4.0)
area('LIGHT | cool window edge',(-4.4,2.7,3.8),(-.7,0,2),1250,'#A6D5E3',2.3)
area('LIGHT | warm camera fill',(3.8,-4.8,4.2),(-.5,.3,2.2),250,'#FFE4C2',3.2)
area('LIGHT | tabletop accent',(2.6,1.0,4),(1.3,-.3,1.5),180,'#FFC36E',1.8)
for i,(x,y,h,r) in enumerate(clusters):
    if i%2:continue
    data=bpy.data.lights.new('LIGHT | fire practical','POINT');data.energy=95;data.color=(1,.20,.035);data.shadow_soft_size=.45
    obj=bpy.data.objects.new(data.name,data);COL['07'].objects.link(obj);obj.location=(x,y,h*.45)
world=bpy.data.worlds.new('WORLD | midnight studio');world.use_nodes=True;scene.world=world
world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.10,.14,.18,1);world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.16
camera_data=bpy.data.cameras.new('CAMERA | showcase');camera=bpy.data.objects.new('CAMERA | showcase',camera_data);COL['07'].objects.link(camera)
camera.location=(6.4,-11.7,6.0);target=Vector((-.10,.65,2.10));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.lens=48;camera_data.dof.use_dof=True;camera_data.dof.focus_object=head;camera_data.dof.aperture_fstop=7.1
scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.device='GPU';scene.cycles.samples=192;scene.cycles.use_adaptive_sampling=True;scene.cycles.adaptive_threshold=.018;scene.cycles.use_denoising=True;scene.cycles.seed=321;scene.cycles.use_animated_seed=False
scene.cycles.max_bounces=7;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=5;scene.cycles.transparent_max_bounces=12;scene.cycles.volume_bounces=1
scene.cycles.sample_clamp_indirect=3
scene.render.resolution_x=1920;scene.render.resolution_y=1280;scene.render.resolution_percentage=100
scene.render.use_persistent_data=False;scene.render.use_compositing=True;scene.render.use_sequencer=False
comp=bpy.data.node_groups.new('FINISH | subtle optical fire glow','CompositorNodeTree')
comp.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
render_layer=comp.nodes.new('CompositorNodeRLayers');render_layer.scene=scene
optical=comp.nodes.new('CompositorNodeGlare');optical.inputs['Type'].default_value='Fog Glow';optical.inputs['Quality'].default_value='High';optical.inputs['Threshold'].default_value=1.0;optical.inputs['Strength'].default_value=.23;optical.inputs['Size'].default_value=.30
comp_out=comp.nodes.new('NodeGroupOutput');comp.links.new(render_layer.outputs['Image'],optical.inputs['Image']);comp.links.new(optical.outputs['Image'],comp_out.inputs['Image'])
scene.compositing_node_group=comp
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='16'
scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
try:scene.view_settings.look='AgX - Medium High Contrast'
except TypeError:pass
scene.view_settings.exposure=-.65
scene.render.filepath=str(HERE/'before.png')
# Real default setup for a customer to inspect and operate, with explicit exclusions.
settings=scene.vram_fixer;settings.reference=body;settings.protect_reference=True;settings.preset='STRONG';settings.textures=True;settings.meshes=True
for key in ('01','03','05','06'):
    for obj in COL[key].objects:
        settings.protected.add().object=obj
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
for screen in bpy.data.screens:
    for area_ in screen.areas:
        if area_.type=='VIEW_3D':
            area_.spaces.active.region_3d.view_perspective='CAMERA'
            area_.spaces.active.overlay.show_overlays=False
            area_.spaces.active.show_region_ui=True
            area_.spaces.active.shading.type='SOLID'
            area_.spaces.active.shading.color_type='MATERIAL'
scene['demo_notes']='Original 3D mascot and set, inspired by the user-supplied burning-room concept. Source texture resolutions intentionally oversized for controlled optimization demonstration. No hard-OOM or universal speedup claim.'
scene['comparison_rule']='Freeze camera, lighting, exposure, render resolution, seed and sampling between BEFORE and AFTER; optimization overhead reported separately.'
bpy.context.view_layer.update()
assert scene.camera and settings.reference and not settings.active_session
assert len([o for o in COL['01'].objects if o.type=='MESH'])>20
assert all(image.packed_file for image in bpy.data.images if image.type in {'IMAGE','UV_TEST'})
summary={'objects':len(scene.objects),'meshes':sum(o.type=='MESH' for o in scene.objects),'curves':sum(o.type=='CURVE' for o in scene.objects),'images':len(bpy.data.images),'protected':len(settings.protected),'source_image_pixels':sum(i.size[0]*i.size[1] for i in bpy.data.images),'reference':body.name,'camera':list(camera.location)}
(HERE/'scene_inventory.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
notes=bpy.data.texts.new('START HERE | VRAM Fixer Showcase');notes.write('KEEP THE SHOT / Burning Room\n\nOriginal native 3D geometry and bakes. Optional speech is in collection 08.\nThe mascot, cup, flame and smoke collections are protected.\nSmall fluted pottery pieces are real high-density mesh candidates.\nMajor textures are deliberately oversized source assets for this controlled demo.\nUse the supplied measured comparison report; never claim a guaranteed speedup or hard-OOM rescue.\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'burning_room_before.blend'),check_existing=False)
print('BURNING_ROOM_BUILT',json.dumps(summary),flush=True)
