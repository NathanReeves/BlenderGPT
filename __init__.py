import sys
import os
import bpy
import bpy.props
import re

# Add the 'libs' folder to the Python path
libs_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
if libs_path not in sys.path:
    sys.path.append(libs_path)

from .utilities import *

bl_info = {
    "name": "Ollama Blender Assistant",
    "blender": (4, 0, 0),
    "category": "Object",
    "author": "Nathan Reeves, Aarya (@gd3kr)",
    "version": (2, 0, 0),
    "location": "3D View > UI > Ollama Blender Assistant",
    "description": "Generate Blender Python code using a local LLM via Ollama.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
}

system_prompt = """You are an assistant made for the purposes of helping the user with Blender, the 3D software. 
- Respond with your answers in markdown (```). 
- Preferably import entire modules instead of bits. 
- Do not perform destructive operations on the meshes. 
- Do not use cap_ends. Do not do more than what is asked (setting up render settings, adding cameras, etc)
- Do not respond with anything that is not Python code.

Example:

user: create 10 cubes in random locations from -10 to 10
assistant:

```
import bpy
import random
bpy.ops.mesh.primitive_cube_add()

#how many cubes you want to add
count = 10

for c in range(0,count):
    x = random.randint(-10,10)
    y = random.randint(-10,10)
    z = random.randint(-10,10)
    bpy.ops.mesh.primitive_cube_add(location=(x,y,z))
```"""




class OLLAMA_OT_DeleteMessage(bpy.types.Operator):
    bl_idname = "ollama.delete_message"
    bl_label = "Delete Message"
    bl_options = {'REGISTER', 'UNDO'}

    message_index: bpy.props.IntProperty()

    def execute(self, context):
        context.scene.ollama_chat_history.remove(self.message_index)
        return {'FINISHED'}

class OLLAMA_OT_ShowCode(bpy.types.Operator):
    bl_idname = "ollama.show_code"
    bl_label = "Show Code"
    bl_options = {'REGISTER', 'UNDO'}

    code: bpy.props.StringProperty(
        name="Code",
        description="The generated code",
        default="",
    )

    def execute(self, context):
        text_name = "Ollama_Generated_Code.py"
        text = bpy.data.texts.get(text_name)
        if text is None:
            text = bpy.data.texts.new(text_name)

        text.clear()
        text.write(self.code)

        text_editor_area = None
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                text_editor_area = area
                break

        if text_editor_area is None:
            text_editor_area = split_area_to_text_editor(context)
        
        text_editor_area.spaces.active.text = text

        return {'FINISHED'}

class OLLAMA_PT_Panel(bpy.types.Panel):
    bl_label = "Ollama Blender Assistant"
    bl_idname = "OLLAMA_PT_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Ollama Assistant'

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        column.label(text="Chat history:")
        box = column.box()
        for index, message in enumerate(context.scene.ollama_chat_history):
            if message.type == 'assistant':
                row = box.row()
                row.label(text="Assistant: ")
                show_code_op = row.operator("ollama.show_code", text="Show Code")
                show_code_op.code = message.content
                delete_message_op = row.operator("ollama.delete_message", text="", icon="TRASH", emboss=False)
                delete_message_op.message_index = index
            else:
                row = box.row()
                row.label(text=f"User: {message.content}")
                delete_message_op = row.operator("ollama.delete_message", text="", icon="TRASH", emboss=False)
                delete_message_op.message_index = index

        column.separator()
        
        column.label(text="Ollama Model:")
        column.prop(context.scene, "ollama_model", text="")

        column.label(text="Enter your message:")
        column.prop(context.scene, "ollama_chat_input", text="")
        button_label = "Please wait...(this might take some time)" if context.scene.ollama_button_pressed else "Execute"
        row = column.row(align=True)
        row.operator("ollama.send_message", text=button_label)
        row.operator("ollama.clear_chat", text="Clear Chat")

        column.separator()

class OLLAMA_OT_ClearChat(bpy.types.Operator):
    bl_idname = "ollama.clear_chat"
    bl_label = "Clear Chat"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.ollama_chat_history.clear()
        return {'FINISHED'}

class OLLAMA_OT_Execute(bpy.types.Operator):
    bl_idname = "ollama.send_message"
    bl_label = "Send Message"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.report({'INFO'}, "Running...")
        context.scene.ollama_button_pressed = True
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        # Make a request to the Ollama embeddings endpoint to get relevant documentation
        url = "http://localhost:11434/api/embeddings"
        headers = {'Content-Type': 'application/json'}
        
        # Get embeddings for the user's query
        payload = {
            "model": "nomic-embed-text",
            "prompt": context.scene.ollama_chat_input
        }
        
        try:
            # Here you would normally do the RAG search, but for now let's use a simplified approach
            # that just includes some basic documentation about the likely operations needed
            docs_context = ""
            query = context.scene.ollama_chat_input.lower()
            
            # Basic pattern matching to include relevant documentation
            if "sphere" in query:
                docs_context = (
                    "bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16, "
                    "location=(0.0, 0.0, 0.0)): Adds a UV sphere mesh to the scene.\n"
                    "Parameters:\n"
                    "  radius: Sets the radius of the sphere\n"
                    "  segments: Number of vertical segments\n"
                    "  ring_count: Number of horizontal rings\n"
                    "  location: Location of the sphere's center\n"
                )
            elif "cube" in query:
                docs_context = (
                    "bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0)): "
                    "Adds a cube mesh to the scene.\n"
                    "Parameters:\n"
                    "  size: Size of the cube\n"
                    "  location: Location of the cube's center\n"
                )
            # Add more patterns as needed...

            blender_code = generate_blender_code(
                context.scene.ollama_chat_input,
                context.scene.ollama_chat_history,
                context,
                system_prompt,
                docs_context,
                self
            )

            # Add the user message to the chat history
            message = context.scene.ollama_chat_history.add()
            message.type = 'user'
            message.content = context.scene.ollama_chat_input

            # Clear the chat input field
            context.scene.ollama_chat_input = ""

            if blender_code:
                message = context.scene.ollama_chat_history.add()
                message.type = 'assistant'
                message.content = blender_code

                # Execute the generated code using a copy of the current globals
                global_namespace = globals().copy()
                try:
                    exec(blender_code, global_namespace)
                except Exception as e:
                    self.report({'ERROR'}, f"Error executing generated code: {e}")
                    context.scene.ollama_button_pressed = False
                    return {'CANCELLED'}
            else:
                self.report({'ERROR'}, "No code was generated!")
                context.scene.ollama_button_pressed = False
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error during execution: {str(e)}")
            context.scene.ollama_button_pressed = False
            return {'CANCELLED'}

        context.scene.ollama_button_pressed = False
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(OLLAMA_OT_Execute.bl_idname)

class OllamaAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        layout.label(text="No API key required for local Ollama usage.")

def register():
    bpy.utils.register_class(OllamaAddonPreferences)
    bpy.utils.register_class(OLLAMA_OT_Execute)
    bpy.utils.register_class(OLLAMA_PT_Panel)
    bpy.utils.register_class(OLLAMA_OT_ClearChat)
    bpy.utils.register_class(OLLAMA_OT_ShowCode)
    bpy.utils.register_class(OLLAMA_OT_DeleteMessage)

    bpy.types.VIEW3D_MT_mesh_add.append(menu_func)
    init_props()

def unregister():
    bpy.utils.unregister_class(OllamaAddonPreferences)
    bpy.utils.unregister_class(OLLAMA_OT_Execute)
    bpy.utils.unregister_class(OLLAMA_PT_Panel)
    bpy.utils.unregister_class(OLLAMA_OT_ClearChat)
    bpy.utils.unregister_class(OLLAMA_OT_ShowCode)
    bpy.utils.unregister_class(OLLAMA_OT_DeleteMessage)

    bpy.types.VIEW3D_MT_mesh_add.remove(menu_func)
    clear_props()

if __name__ == "__main__":
    register()
