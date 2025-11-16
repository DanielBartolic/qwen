FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-ubuntu24.04

WORKDIR /

# Install system dependencies (git and wget should already be there, but just in case)
RUN apt-get update && apt-get install -y \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Clone ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git

WORKDIR /ComfyUI

# Install ComfyUI requirements (skip torch since it's already installed)
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir packaging

# Clone all custom nodes
WORKDIR /ComfyUI/custom_nodes

RUN git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts && \
    git clone https://github.com/rgthree/rgthree-comfy && \
    git clone https://github.com/Jonseed/ComfyUI-Detail-Daemon && \
    git clone https://github.com/ClownsharkBatwing/RES4LYF && \
    git clone https://github.com/digitaljohn/comfyui-propost && \
    git clone https://github.com/gseth/ControlAltAI-Nodes && \
    git clone https://github.com/WASasquatch/was-node-suite-comfyui && \
    git clone https://github.com/M1kep/ComfyLiterals

# Install requirements for all custom nodes
RUN for dir in */ ; do \
        if [ -f "$dir/requirements.txt" ]; then \
            echo "Installing requirements from $dir" && \
            pip install --no-cache-dir -r "$dir/requirements.txt" || true; \
        fi; \
        if [ -f "$dir/install.py" ]; then \
            echo "Running install.py in $dir" && \
            cd "$dir" && python install.py && cd ..; \
        fi; \
    done

WORKDIR /ComfyUI

# Download models
RUN mkdir -p models/diffusion_models models/loras models/vae models/text_encoders

RUN wget -q --show-progress -P models/diffusion_models/ \
    https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_bf16.safetensors

RUN wget -q --show-progress -P models/loras/ \
    https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V2.0.safetensors

RUN wget -q --show-progress -P models/vae/ \
    https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors

RUN wget -q --show-progress -P models/text_encoders/ \
    https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors

# Copy your handler
COPY src/handler.py /handler.py

CMD ["python", "-u", "/handler.py"]