import bpy
import re
import os
import sys
import json
import requests

def init_props():
    # First, create a custom PropertyGroup class
    class OllamaChatMessage(bpy.types.PropertyGroup):
        type: bpy.props.StringProperty()
        content: bpy.props.StringProperty()
    
    # Register the class
    bpy.utils.register_class(OllamaChatMessage)
    
    # Add model selector
    bpy.types.Scene.ollama_model = bpy.props.EnumProperty(
        name="Ollama Model",
        description="Select the Ollama model to use",
        items=[
            ("qwen2.5-coder:32b", "Qwen 2.5 Coder (32B)", "Use Qwen 2.5 Coder model"),
            ("codellama:34b", "CodeLlama (34B)", "Use CodeLlama model"),
            ("deepseek-coder:33b", "DeepSeek Coder (33B)", "Use DeepSeek Coder model")
        ],
        default="qwen2.5-coder:32b",
    )
    
    # Then use it in the collection property
    bpy.types.Scene.ollama_chat_history = bpy.props.CollectionProperty(type=OllamaChatMessage)
    bpy.types.Scene.ollama_chat_input = bpy.props.StringProperty(
        name="Message",
        description="Enter your message",
        default="",
    )
    bpy.types.Scene.ollama_button_pressed = bpy.props.BoolProperty(default=False)

def clear_props():
    # Unregister the class when clearing props
    bpy.utils.unregister_class(bpy.types.OllamaChatMessage)
    del bpy.types.Scene.ollama_chat_history
    del bpy.types.Scene.ollama_chat_input
    del bpy.types.Scene.ollama_button_pressed
    del bpy.types.Scene.ollama_model

def generate_blender_code(prompt, chat_history, context, system_prompt, operator=None):
    # Get the selected model
    model_name = context.scene.ollama_model

    # Build the conversation prompt from the system prompt and chat history
    conversation = system_prompt + "\n\n"
    for message in chat_history[-10:]:
        if message.type == "assistant":
            conversation += "Assistant:\n" + message.content + "\n\n"
        else:
            conversation += "User:\n" + message.content + "\n\n"
    conversation += "You are an expert in Blender's Python API. Please write Blender code that accomplishes the following task: " + prompt + "? \n. Do not respond with anything that is not Python code. Do not provide explanations"
    conversation += "Assistant:\n"

    # Set up the Ollama API request
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": conversation,
        "stream": False
    }

    try:
        if operator:
            operator.report({'INFO'}, "=== Debug Information ===")
            operator.report({'INFO'}, f"URL: {url}")
            operator.report({'INFO'}, f"Headers: {{'Content-Type': 'application/json'}}")
            operator.report({'INFO'}, f"Full payload: {json.dumps(payload, indent=2)}")
        
        # Explicitly set the Content-Type header
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, json=payload, headers=headers)
        
        if operator:
            operator.report({'INFO'}, f"Response status: {response.status_code}")
            operator.report({'INFO'}, f"Response text: {response.text[:200]}")  # First 200 chars
        
        response.raise_for_status()
        
        # Parse the JSON response and log it
        response_data = response.json()
        if operator:
            operator.report({'INFO'}, f"Raw response: {response_data}")
        
        completion_text = response_data.get("response", "")
        if operator:
            operator.report({'INFO'}, f"Completion text: {completion_text[:100]}...")  # First 100 chars
        
        # Try to extract code enclosed in markdown code blocks
        matches = re.findall(r'```(?:python)?(.*?)```', completion_text, re.DOTALL)
        if matches:
            code = matches[0].strip()
            if operator:
                operator.report({'INFO'}, f"Found code block: {code[:100]}...")
        else:
            code = completion_text.strip()
            if operator:
                operator.report({'INFO'}, "No code blocks found in response")
                operator.report({'INFO'}, f"Using raw text: {code[:100]}...")
            
        # Remove any "python" language identifier if present
        code = re.sub(r'^python\n', '', code, flags=re.MULTILINE)
        
        if not code:
            if operator:
                operator.report({'ERROR'}, "Generated code is empty")
            return None
            
        return code

    except requests.exceptions.RequestException as e:
        if operator:
            operator.report({'ERROR'}, f"Network error: {str(e)}")
        else:
            print(f"Network error: {str(e)}")  # Fallback for when operator is None
        return None
    except json.JSONDecodeError as e:
        if operator:
            operator.report({'ERROR'}, f"JSON parsing error: {str(e)}")
        else:
            print(f"JSON parsing error: {str(e)}")
        return None
    except Exception as e:
        if operator:
            operator.report({'ERROR'}, f"Unexpected error: {str(e)}")
        else:
            print(f"Unexpected error: {str(e)}")
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
