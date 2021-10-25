"""
    Copyright (C) 2021 Project Studio Q inc.

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 2
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import bpy
import bgl
import gpu
import blf
import mathutils
from gpu_extras.batch import batch_for_shader

# -----------------------------------------------------------------------------

DEBUG_MODE = False
enabled = False

# -----------------------------------------------------------------------------

class QANIM_PT_animation_shift(bpy.types.Panel):
    """
        アニメーション シフト変更機能
    """
    bl_label = "Animation Offset Shift"
    bl_idname = "QANIM_PT_animation_shift"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q_ANIM"
    bl_options = {'DEFAULT_CLOSED'}

    def draw( self, context ):
        scene = context.scene
        layout = self.layout

        layout.prop( scene, "temp_animation_shift" )

# -----------------------------------------------------------------------------

saved_deform = {}

@bpy.app.handlers.persistent
def _stop_update( self, context ):
    global enabled
    enabled = False

@bpy.app.handlers.persistent
def _init_deform( self, context ):
    if DEBUG_MODE:
        print( "init" )

    global saved_deform
    saved_deform.clear( )

    for obj in bpy.data.objects:
        if obj.animation_data is None:
            continue
        if obj.animation_data.action is None:
            continue

        action = obj.animation_data.action

        saved_deform[obj.name] = {}

        for fc in action.fcurves:
            path = "%s[%d]" % ( fc.data_path, fc.array_index )
            # TODO: evalじゃない方法に変更したい。evalはpathに何が入ってるかわからないので危険すぎる
            # もしくは pathが制限付きPython Expressionをパスできるか否かをチェックする？
            try:
                if DEBUG_MODE:
                    print( 'obj.' + path, eval( 'obj.' + path ) )
                saved_deform[obj.name][path] = eval( 'obj.' + path )
            except Exception as e:
                if DEBUG_MODE:
                    print( "Exception in animation key shift init: ", e )

    global enabled
    enabled = True

    if DEBUG_MODE:
        print( " -> init END" )

@bpy.app.handlers.persistent
def _update_deform( self, depsgraph ):
    global enabled
    if not enabled:
        return

    if not hasattr( bpy.context.screen, "is_animation_playing" ) or bpy.context.screen.is_animation_playing:
        return
    if not hasattr( bpy.context.scene, "temp_animation_shift" ) or not bpy.context.scene.temp_animation_shift:
        return

    if DEBUG_MODE:
        print( "update" )

    global saved_deform

    def apply_to_fcurve( obj, fc ):
        path = "%s[%d]" % ( fc.data_path, fc.array_index )
        if path not in saved_deform[obj.name]:
            return

        # TODO: evalじゃない方法に変更したい。evalはpathに何が入ってるかわからないので危険すぎる
        # もしくは pathが制限付きPython Expressionをパスできるか否かをチェックする？
        diff = 0.0
        try:
            new_val = eval( 'obj.' + path )
            diff = new_val - saved_deform[obj.name][path]
            if DEBUG_MODE:
                print( 'obj.' + path, new_val, diff )
        except Exception as e:
            # Evalの例外を無視する
            if DEBUG_MODE:
                print( "Exception in animation key shift update: ", e )

        if 0.0 < abs( diff ):
            for key in fc.keyframe_points:
                if DEBUG_MODE:
                    print( obj.as_pointer( ), ":", obj.name, ":", fc.as_pointer( ), ":", path, " -> ", key.co, key.handle_left, key.handle_right, diff )
                key.co.y += diff
                key.handle_left.y += diff
                key.handle_right.y += diff

    for du in depsgraph.updates:
        obj = du.id.original
        if not isinstance( obj, bpy.types.Object ):
            continue
        if obj.type != "ARMATURE":
            continue
        if obj.animation_data is None:
            continue
        if obj.original is not bpy.context.active_object:
            continue
        if obj.animation_data.action is None:
            continue

        # Action側の処理
        action = obj.animation_data.action
        if DEBUG_MODE:
            print( action.name )

        for fc in action.fcurves:
            apply_to_fcurve( obj, fc )

    if DEBUG_MODE:
        print( " -> update END" )

    _init_deform( self, bpy.context )

# -----------------------------------------------------------------------------

def _draw( ):
    if _init_deform not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append( _init_deform )
    if _update_deform not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append( _update_deform )

    scene = bpy.context.scene

    if not hasattr( scene, "temp_animation_shift" ) or not hasattr( scene, "temp_use_keyframe_insert_auto" ):
        return

    if scene.temp_animation_shift:
        bpy.context.tool_settings.use_keyframe_insert_auto = False

        blf.size( 0, 32, 72 )
        blf.position( 0, 16, 16, 0 )
        blf.color( 0, 1.0, 0.0, 0.0, 1.0 )
        blf.draw( 0, "!! Animation Offset Shift Enabled !!" )

def _update_temp_animation_shift( self, context ):
    scene = bpy.context.scene

    if not hasattr( scene, "temp_animation_shift" ) or not hasattr( scene, "temp_use_keyframe_insert_auto" ):
        return

    if scene.temp_animation_shift:
        scene.temp_use_keyframe_insert_auto = bpy.context.tool_settings.use_keyframe_insert_auto
        bpy.context.tool_settings.use_keyframe_insert_auto = False
    else:
        bpy.context.tool_settings.use_keyframe_insert_auto = scene.temp_use_keyframe_insert_auto

# -----------------------------------------------------------------------------

classes = (
    QANIM_PT_animation_shift,
)
_func_handler_display_handle = None

def register():
    """
        クラス登録
    """
    for i in classes:
        bpy.utils.register_class(i)

    _initialized( )

def unregister():
    """
        クラス登録解除
    """
    _deinitialized( )

    for i in classes:
        bpy.utils.unregister_class(i)

def _initialized( ):
    """
        初期化
    """
    bpy.types.Scene.temp_animation_shift = bpy.props.BoolProperty( name="Animation Offset Shift Enable", default= False, update=_update_temp_animation_shift )
    bpy.types.Scene.temp_use_keyframe_insert_auto = bpy.props.BoolProperty( name="Original Timeline's Auto Keying", default= False )

    bpy.app.handlers.load_pre.append( _stop_update )
    bpy.app.handlers.redo_pre.append( _stop_update )
    bpy.app.handlers.undo_pre.append( _stop_update )
    bpy.app.handlers.frame_change_pre.append( _stop_update )
    #bpy.app.handlers.depsgraph_update_pre.append( _stop_update )

    bpy.app.handlers.load_post.append( _init_deform )
    bpy.app.handlers.redo_post.append( _init_deform )
    bpy.app.handlers.undo_post.append( _init_deform )

    global _func_handler_display_handle
    _func_handler_display_handle = bpy.types.SpaceView3D.draw_handler_add( _draw, (), 'WINDOW', 'POST_PIXEL' )

def _deinitialized( ):
    """
        後始末
    """
    del bpy.types.Scene.temp_animation_shift
    del bpy.types.Scene.temp_use_keyframe_insert_auto

    global _func_handler_display_handle
    if _func_handler_display_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove( _func_handler_display_handle, 'WINDOW' )

