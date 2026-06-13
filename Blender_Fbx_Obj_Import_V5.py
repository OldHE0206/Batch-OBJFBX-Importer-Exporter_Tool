# ============================================================
# Batch Import & Export Add-on for Blender 5.0
# Supports batch import of OBJ/FBX files from a folder (including ZIP archives),
# and batch export of mesh objects to individual OBJ/FBX files.
# Author: AI Assistant
# ============================================================

bl_info = {
    "name": "Batch OBJ/FBX Importer & Exporter",
    "author": "Your Name",
    "version": (1, 3),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Sidebar (N-Panel) > Import/Export Tools",
    "description": "批量导入/导出 OBJ 和 FBX 文件，支持自动解压 ZIP 压缩包",
    "category": "Import-Export",
}

import bpy
import os
import zipfile


# -------------------------------------------------------------------
# 辅助函数
# -------------------------------------------------------------------
def extract_zip_files(folder_path, report_func):
    """解压 folder_path 下所有 .zip 文件到同一文件夹（覆盖已存在的文件）"""
    if not os.path.isdir(folder_path):
        return 0, []
    zip_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.zip')]
    if not zip_files:
        return 0, []
    
    success_count = 0
    failed_zips = []
    for zip_name in zip_files:
        zip_path = os.path.join(folder_path, zip_name)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(folder_path)
            success_count += 1
            report_func({'INFO'}, f"解压成功: {zip_name}")
        except Exception as e:
            failed_zips.append(f"{zip_name}: {str(e)}")
            report_func({'WARNING'}, f"解压失败 {zip_name}: {str(e)}")
    return success_count, failed_zips


def find_all_mesh_files(root_folder):
    """递归查找 root_folder 下所有的 .obj 和 .fbx 文件，返回文件路径列表"""
    mesh_files = []
    for dirpath, dirnames, filenames in os.walk(root_folder):
        for f in filenames:
            f_lower = f.lower()
            if f_lower.endswith(('.obj', '.fbx')):
                mesh_files.append(os.path.join(dirpath, f))
    return mesh_files


# -------------------------------------------------------------------
# 导入相关类
# -------------------------------------------------------------------

class BATCH_IMPORT_OT_folder_selector(bpy.types.Operator):
    """选择包含 OBJ/FBX 文件的文件夹"""

    bl_idname = "batch_import.select_folder"
    bl_label = "选择导入文件夹"
    bl_description = "选择包含OBJ/FBX文件的文件夹（将自动解压其中的ZIP文件）"

    directory: bpy.props.StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        scene = context.scene
        props = scene.batch_import_props
        props.folder_path = self.directory
        self.refresh_file_list(context)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def refresh_file_list(self, context):
        scene = context.scene
        props = scene.batch_import_props
        props.file_list.clear()
        folder = bpy.path.abspath(props.folder_path)
        if os.path.isdir(folder):
            # 递归查找所有模型文件（用于显示列表）
            all_files = find_all_mesh_files(folder)
            for file_path in all_files:
                rel_path = os.path.relpath(file_path, folder)
                ext = 'OBJ' if file_path.lower().endswith('.obj') else 'FBX'
                item = props.file_list.add()
                item.name = rel_path
                item.type = ext
                item.file_path = file_path
            if all_files:
                self.report({'INFO'}, f"找到 {len(all_files)} 个模型文件")
            else:
                self.report({'WARNING'}, "文件夹中没有找到 OBJ 或 FBX 文件")
        else:
            self.report({'ERROR'}, "无效的文件夹路径")


class BATCH_IMPORT_OT_import_all(bpy.types.Operator):
    """批量导入所有文件（自动解压ZIP）"""

    bl_idname = "batch_import.import_all"
    bl_label = "批量导入"
    bl_description = "导入文件夹中的所有 OBJ 和 FBX 文件（自动解压 ZIP 压缩包）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.batch_import_props
        folder = bpy.path.abspath(props.folder_path)

        if not folder or not os.path.isdir(folder):
            self.report({'ERROR'}, "请先选择有效的文件夹！")
            return {'CANCELLED'}

        # 1. 解压所有 ZIP 文件
        extracted_count, failed_zips = extract_zip_files(folder, self.report)
        if extracted_count:
            self.report({'INFO'}, f"已解压 {extracted_count} 个 ZIP 文件")
        if failed_zips:
            self.report({'WARNING'}, f"{len(failed_zips)} 个 ZIP 解压失败")

        # 2. 递归查找所有模型文件
        files_to_import = find_all_mesh_files(folder)

        if not files_to_import:
            self.report({'WARNING'}, "文件夹中没有找到 OBJ 或 FBX 文件（解压后也没有）")
            return {'CANCELLED'}

        # 3. 批量导入
        success_count = 0
        failed_count = 0
        failed_files = []

        for i, filepath in enumerate(files_to_import):
            self.report({'INFO'}, f"正在导入 ({i+1}/{len(files_to_import)}): {os.path.basename(filepath)}")
            try:
                ext = os.path.splitext(filepath)[1].lower()
                if ext == '.obj':
                    bpy.ops.wm.obj_import(filepath=filepath)
                elif ext == '.fbx':
                    bpy.ops.wm.fbx_import(filepath=filepath)
                success_count += 1
            except Exception as e:
                failed_count += 1
                failed_files.append(f"{os.path.basename(filepath)}: {str(e)}")
                self.report({'WARNING'}, f"导入失败 {os.path.basename(filepath)}: {str(e)}")

        self.report({'INFO'}, f"导入完成！成功: {success_count}, 失败: {failed_count}")
        if failed_files and props.show_errors:
            error_msg = "\n".join(failed_files)
            self.report({'ERROR'}, error_msg[:512])
        return {'FINISHED'}


class BATCH_IMPORT_OT_clear_folder(bpy.types.Operator):
    """清空导入文件夹路径"""

    bl_idname = "batch_import.clear_folder"
    bl_label = "清空"
    bl_description = "清空当前导入文件夹路径"

    def execute(self, context):
        props = context.scene.batch_import_props
        props.folder_path = ""
        props.file_list.clear()
        self.report({'INFO'}, "已清空导入文件夹路径")
        return {'FINISHED'}


class BATCH_IMPORT_OT_refresh_list(bpy.types.Operator):
    """刷新导入文件列表（并自动解压ZIP）"""

    bl_idname = "batch_import.refresh_list"
    bl_label = "刷新"
    bl_description = "刷新当前导入文件夹的文件列表（自动解压ZIP）"

    def execute(self, context):
        scene = context.scene
        props = scene.batch_import_props
        folder = bpy.path.abspath(props.folder_path)
        props.file_list.clear()
        if not folder or not os.path.isdir(folder):
            self.report({'WARNING'}, "请先选择有效的文件夹")
            return {'CANCELLED'}

        # 刷新前先解压 ZIP 文件
        extracted_count, failed_zips = extract_zip_files(folder, self.report)
        if extracted_count:
            self.report({'INFO'}, f"已解压 {extracted_count} 个 ZIP 文件")
        if failed_zips:
            self.report({'WARNING'}, f"{len(failed_zips)} 个 ZIP 解压失败")

        # 递归查找所有模型文件并显示在列表中
        all_files = find_all_mesh_files(folder)
        for file_path in all_files:
            rel_path = os.path.relpath(file_path, folder)
            ext = 'OBJ' if file_path.lower().endswith('.obj') else 'FBX'
            item = props.file_list.add()
            item.name = rel_path
            item.type = ext
            item.file_path = file_path

        if all_files:
            self.report({'INFO'}, f"找到 {len(all_files)} 个模型文件")
        else:
            self.report({'WARNING'}, "文件夹中没有找到 OBJ 或 FBX 文件")
        return {'FINISHED'}


class BATCH_IMPORT_UL_file_list(bpy.types.UIList):
    """导入文件列表 UI"""

    bl_idname = "BATCH_IMPORT_UL_file_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.name)
            if item.type == 'OBJ':
                row.label(text="OBJ", icon='MESH_DATA')
            else:
                row.label(text="FBX", icon='MESH_CUBE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_BLEND')


class BATCH_IMPORT_FileItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="文件名")
    type: bpy.props.StringProperty(name="文件类型")
    file_path: bpy.props.StringProperty(name="文件路径")


class BATCH_IMPORT_Properties(bpy.types.PropertyGroup):
    folder_path: bpy.props.StringProperty(
        name="导入文件夹路径",
        subtype="DIR_PATH",
        default="",
    )
    file_list: bpy.props.CollectionProperty(type=BATCH_IMPORT_FileItem)
    file_list_index: bpy.props.IntProperty(default=0)
    show_errors: bpy.props.BoolProperty(
        name="显示详细错误",
        default=True,
    )


# -------------------------------------------------------------------
# 导出相关类
# -------------------------------------------------------------------

class BATCH_EXPORT_Properties(bpy.types.PropertyGroup):
    export_folder_path: bpy.props.StringProperty(
        name="导出文件夹路径",
        subtype="DIR_PATH",
        default="",
    )
    export_format: bpy.props.EnumProperty(
        name="导出格式",
        items=[
            ('FBX', "FBX", "导出为 FBX 格式"),
            ('OBJ', "OBJ", "导出为 OBJ 格式"),
        ],
        default='FBX',
    )
    export_selected_only: bpy.props.BoolProperty(
        name="仅导出选中物体",
        description="仅导出当前选中的物体，否则导出场景中所有网格物体",
        default=False,
    )


class BATCH_EXPORT_OT_folder_selector(bpy.types.Operator):
    """选择导出目标文件夹"""

    bl_idname = "batch_export.select_folder"
    bl_label = "选择导出文件夹"
    bl_description = "选择保存导出文件的文件夹"

    directory: bpy.props.StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        context.scene.batch_export_props.export_folder_path = self.directory
        self.report({'INFO'}, f"导出文件夹已设置为: {self.directory}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class BATCH_EXPORT_OT_clear_folder(bpy.types.Operator):
    """清空导出文件夹路径"""

    bl_idname = "batch_export.clear_folder"
    bl_label = "清空"
    bl_description = "清空当前导出文件夹路径"

    def execute(self, context):
        context.scene.batch_export_props.export_folder_path = ""
        self.report({'INFO'}, "已清空导出文件夹路径")
        return {'FINISHED'}


class BATCH_EXPORT_OT_export_all(bpy.types.Operator):
    """批量导出所有网格物体"""

    bl_idname = "batch_export.export_all"
    bl_label = "开始批量导出"
    bl_description = "将每个网格物体导出为单独的文件"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.batch_export_props
        export_dir = bpy.path.abspath(props.export_folder_path)

        if not export_dir or not os.path.isdir(export_dir):
            self.report({'ERROR'}, "请先选择有效的导出文件夹！")
            return {'CANCELLED'}

        # 确定要导出的物体列表
        if props.export_selected_only:
            objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        else:
            objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']

        if not objects:
            self.report({'WARNING'}, "没有找到可导出的网格物体")
            return {'CANCELLED'}

        # 保存原始选择状态
        original_selection = context.selected_objects.copy()
        original_active = context.active_object

        success_count = 0
        failed_objects = []

        for obj in objects:
            file_name = obj.name
            # 移除文件名中可能导致问题的字符
            safe_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
            if not safe_name:
                safe_name = "unnamed"

            if props.export_format == 'FBX':
                ext = ".fbx"
                # Blender 中 FBX 导出操作符
                export_func = bpy.ops.export_scene.fbx
                # 参数：filepath, use_selection
                kwargs = {'filepath': os.path.join(export_dir, safe_name + ext), 'use_selection': True}
            else:  # OBJ
                ext = ".obj"
                # Blender 中 OBJ 导出操作符（注意不是 export_scene.obj）
                export_func = bpy.ops.wm.obj_export
                # 参数：filepath, export_selected_objects (新版本)
                kwargs = {'filepath': os.path.join(export_dir, safe_name + ext), 'export_selected_objects': True}

            # 临时仅选中当前物体
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            try:
                # 调用对应的导出操作符
                export_func(**kwargs)
                success_count += 1
                self.report({'INFO'}, f"已导出: {file_name}")
            except Exception as e:
                failed_objects.append(f"{file_name}: {str(e)}")
                self.report({'WARNING'}, f"导出失败 {file_name}: {str(e)}")

        # 恢复原始选择状态
        bpy.ops.object.select_all(action='DESELECT')
        for obj in original_selection:
            obj.select_set(True)
        if original_active:
            context.view_layer.objects.active = original_active

        self.report({'INFO'}, f"批量导出完成！成功: {success_count}, 失败: {len(failed_objects)}")
        if failed_objects:
            error_msg = "\n".join(failed_objects)
            self.report({'ERROR'}, error_msg[:512])

        return {'FINISHED'}


# -------------------------------------------------------------------
# UI 面板
# -------------------------------------------------------------------

class BATCH_IMPORT_PT_panel(bpy.types.Panel):
    bl_label = "批量导入/导出工具"
    bl_idname = "BATCH_IMPORT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "导入导出工具"

    def draw(self, context):
        layout = self.layout
        # 导入区域
        box = layout.box()
        col = box.column(align=True)
        col.label(text="批量导入", icon='IMPORT')
        self.draw_import_ui(context, col)

        # 导出区域
        box = layout.box()
        col = box.column(align=True)
        col.label(text="批量导出", icon='EXPORT')
        self.draw_export_ui(context, col)

    def draw_import_ui(self, context, layout):
        props = context.scene.batch_import_props
        row = layout.row(align=True)
        row.prop(props, "folder_path", text="")
        row = layout.row(align=True)
        row.operator("batch_import.select_folder", text="浏览", icon='FILEBROWSER')
        row.operator("batch_import.clear_folder", text="清空", icon='X')
        row.operator("batch_import.refresh_list", text="刷新", icon='FILE_REFRESH')

        if props.folder_path:
            if props.file_list:
                row = layout.row()
                row.template_list("BATCH_IMPORT_UL_file_list", "",
                                  props, "file_list",
                                  props, "file_list_index", rows=5)
            else:
                layout.label(text="未找到 OBJ/FBX 文件", icon='INFO')
            layout.prop(props, "show_errors")
            layout.operator("batch_import.import_all", text="开始批量导入", icon='IMPORT')
        else:
            layout.label(text="请先选择导入文件夹", icon='ERROR')

    def draw_export_ui(self, context, layout):
        props = context.scene.batch_export_props
        row = layout.row(align=True)
        row.prop(props, "export_folder_path", text="")
        row = layout.row(align=True)
        row.operator("batch_export.select_folder", text="浏览", icon='FILEBROWSER')
        row.operator("batch_export.clear_folder", text="清空", icon='X')
        layout.prop(props, "export_format")
        layout.prop(props, "export_selected_only")
        if props.export_folder_path:
            layout.operator("batch_export.export_all", text="开始批量导出", icon='EXPORT')
        else:
            layout.label(text="请先选择导出文件夹", icon='ERROR')


# -------------------------------------------------------------------
# 注册与注销
# -------------------------------------------------------------------

classes = [
    # 导入相关
    BATCH_IMPORT_FileItem,
    BATCH_IMPORT_Properties,
    BATCH_IMPORT_UL_file_list,
    BATCH_IMPORT_OT_folder_selector,
    BATCH_IMPORT_OT_import_all,
    BATCH_IMPORT_OT_clear_folder,
    BATCH_IMPORT_OT_refresh_list,
    # 导出相关
    BATCH_EXPORT_Properties,
    BATCH_EXPORT_OT_folder_selector,
    BATCH_EXPORT_OT_clear_folder,
    BATCH_EXPORT_OT_export_all,
    # 面板
    BATCH_IMPORT_PT_panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.batch_import_props = bpy.props.PointerProperty(type=BATCH_IMPORT_Properties)
    bpy.types.Scene.batch_export_props = bpy.props.PointerProperty(type=BATCH_EXPORT_Properties)

def unregister():
    del bpy.types.Scene.batch_import_props
    del bpy.types.Scene.batch_export_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()