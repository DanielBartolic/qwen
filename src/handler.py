import runpod
import json
import urllib.request
import urllib.parse
import time
import subprocess
import os
import base64
import random

# Global variables
COMFY_HOST = "127.0.0.1:8188"
comfy_process = None

def start_comfyui():
    """Start ComfyUI server in the background"""
    global comfy_process
    
    print("Starting ComfyUI server...")
    comfy_process = subprocess.Popen(
        ["python", "main.py", "--listen", "127.0.0.1", "--port", "8188"],
        cwd="/ComfyUI",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            urllib.request.urlopen(f"http://{COMFY_HOST}/system_stats")
            print("ComfyUI server is ready!")
            return True
        except:
            time.sleep(2)
            print(f"Waiting for ComfyUI to start... ({i+1}/{max_retries})")
    
    raise Exception("ComfyUI failed to start")

def load_workflow():
    """Load the workflow JSON template"""
    workflow_path = "/ComfyUI/workflows/qwen_sfw_workflow_api.json"
    with open(workflow_path, "r") as f:
        return json.load(f)

def update_workflow(workflow, prompt, width, height, seed, steps):
    """Update workflow with user inputs"""
    # Update prompt (node 231)
    workflow["231"]["inputs"]["String"] = prompt
    
    # Update width (node 91)
    workflow["91"]["inputs"]["Number"] = str(width)
    
    # Update height (node 92)
    workflow["92"]["inputs"]["Number"] = str(height)
    
    # Update seed and steps (node 75)
    workflow["75"]["inputs"]["seed"] = seed
    workflow["75"]["inputs"]["steps"] = steps
    
    return workflow

def queue_prompt(workflow):
    """Send workflow to ComfyUI queue"""
    data = json.dumps({"prompt": workflow}).encode('utf-8')
    req = urllib.request.Request(
        f"http://{COMFY_HOST}/prompt",
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    response = urllib.request.urlopen(req)
    return json.loads(response.read())

def get_history(prompt_id):
    """Get the history/status of a prompt"""
    url = f"http://{COMFY_HOST}/history/{prompt_id}"
    response = urllib.request.urlopen(url)
    return json.loads(response.read())

def wait_for_completion(prompt_id, timeout=300):
    """Wait for the prompt to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        history = get_history(prompt_id)
        
        if prompt_id in history:
            return history[prompt_id]
        
        time.sleep(1)
    
    raise Exception(f"Timeout waiting for prompt {prompt_id}")

def get_image(filename, subfolder, folder_type):
    """Retrieve generated image from ComfyUI"""
    params = urllib.parse.urlencode({
        "filename": filename,
        "subfolder": subfolder,
        "type": folder_type
    })
    url = f"http://{COMFY_HOST}/view?{params}"
    response = urllib.request.urlopen(url)
    return response.read()

def handler(job):
    """Main handler function for RunPod"""
    job_input = job["input"]
    
    # Extract inputs with defaults
    prompt = job_input.get("prompt", "a beautiful landscape")
    width = job_input.get("width", 1440)
    height = job_input.get("height", 1920)
    seed = job_input.get("seed", random.randint(0, 2**32 - 1))
    steps = job_input.get("steps", 25)
    
    # Validate inputs
    if not isinstance(prompt, str) or len(prompt.strip()) == 0:
        return {"error": "Invalid prompt. Please provide a non-empty string."}
    
    if not isinstance(width, int) or width < 64 or width > 4096:
        return {"error": "Invalid width. Must be between 64 and 4096."}
    
    if not isinstance(height, int) or height < 64 or height > 4096:
        return {"error": "Invalid height. Must be between 64 and 4096."}
    
    if not isinstance(steps, int) or steps < 1 or steps > 100:
        return {"error": "Invalid steps. Must be between 1 and 100."}
    
    try:
        # Load and update workflow
        workflow = load_workflow()
        workflow = update_workflow(workflow, prompt, width, height, seed, steps)
        
        # Queue the prompt
        runpod.serverless.progress_update(job, "Queuing prompt...")
        queue_response = queue_prompt(workflow)
        prompt_id = queue_response["prompt_id"]
        
        # Wait for completion
        runpod.serverless.progress_update(job, "Generating image...")
        history = wait_for_completion(prompt_id)
        
        # Get the output image
        outputs = history.get("outputs", {})
        
        # Find the SaveImage node output (node 60)
        if "60" not in outputs:
            return {"error": "No output image found"}
        
        images = outputs["60"].get("images", [])
        if not images:
            return {"error": "No images generated"}
        
        # Get the first image
        image_info = images[0]
        image_data = get_image(
            image_info["filename"],
            image_info.get("subfolder", ""),
            image_info.get("type", "output")
        )
        
        # Convert to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        return {
            "image": image_base64,
            "seed": seed,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps
        }
        
    except Exception as e:
        return {"error": str(e)}

# Initialize ComfyUI when worker starts (outside handler for efficiency)
start_comfyui()

# Start the serverless worker
runpod.serverless.start({"handler": handler})