import bpy
import re
import os
import sys
import json
import requests

def init_props():
    bpy.types.Scene.gpt4_chat_history = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    bpy.types.Scene.gpt4_model = bpy.props.EnumProperty(
        name="GPT Model",
        description="Select the GPT model to use (Ignored in Ollama mode, defaulting to llama3.2b)",
        items=[
            ("gpt-4", "GPT-4 (powerful, expensive)", "Use GPT-4"),
            ("gpt-3.5-turbo", "GPT-3.5 Turbo (less powerful, cheaper)", "Use GPT-3.5 Turbo"),
            ("o1-mini", "o1-mini (Advanced Reasoning)", "Use OpenAI's o1-mini model")
        ],
        default="gpt-4",
    )
    bpy.types.Scene.gpt4_chat_input = bpy.props.StringProperty(
        name="Message",
        description="Enter your message",
        default="",
    )
    bpy.types.Scene.gpt4_button_pressed = bpy.props.BoolProperty(default=False)
    bpy.types.PropertyGroup.type = bpy.props.StringProperty()
    bpy.types.PropertyGroup.content = bpy.props.StringProperty()

def clear_props():
    del bpy.types.Scene.gpt4_chat_history
    del bpy.types.Scene.gpt4_chat_input
    del bpy.types.Scene.gpt4_button_pressed

def generate_blender_code(prompt, chat_history, context, system_prompt):
    # Build the conversation prompt from the system prompt and chat history.
    conversation = system_prompt + "\n\n"
    for message in chat_history[-10:]:
        if message.type == "assistant":
            conversation += "Assistant:\n" + message.content + "\n\n"
        else:
            conversation += "User:\n" + message.content + "\n\n"
    conversation += "User: Can you please write Blender code for me that accomplishes the following task: " + prompt + "?\n"
    conversation += "Assistant:\n"

    # Set up the Ollama API request (adjust the URL if necessary).
    url = "http://localhost:11434/api/generate"
    payload = {
         "model": "llama3.2b",  # Hard-coded for now; you could map context.scene.gpt4_model if needed.
         "prompt": conversation,
         "max_tokens": 1500,
         "stream": True
    }
    try:
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
    except Exception as e:
        print("Error contacting Ollama API:", e)
        return None

    completion_text = ""
    try:
        # Process the streamed response line-by-line.
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                data = json.loads(decoded_line)
                text_chunk = data.get("text", "")
                completion_text += text_chunk
                print(completion_text, flush=True, end='\r')
        # Try to extract code enclosed in markdown code blocks.
        matches = re.findall(r'```(.*?)```', completion_text, re.DOTALL)
        if matches:
            code = matches[0]
        else:
            code = completion_text
        code = re.sub(r'^python', '', code, flags=re.MULTILINE)
        return code
    except Exception as e:
        print("Error processing Ollama response:", e)
        return None

def split_area_to_text_editor(context):
    area = context.area
    for region in area.regions:
        if region.type == 'WINDOW':
            override = {'area': area, 'region': region}
            bpy.ops.screen.area_split(override, direction='VERTICAL', factor=0.5)
            break

    new_area = context.screen.areas[-1]
    new_area.type = 'TEXT_EDITOR'
    return new_area
