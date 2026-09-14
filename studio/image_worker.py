"""This process exits after a batch, releasing RAM and VRAM before text regeneration."""
import os
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
import json
import sys
from pathlib import Path
import torch
from diffusers import StableDiffusionXLPipeline, EulerDiscreteScheduler

if __name__ == '__main__':
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA недоступна. Проверьте установку PyTorch и драйвер NVIDIA.')
    root = Path(__file__).resolve().parents[1]
    pipe = StableDiffusionXLPipeline.from_pretrained(str(root / 'models/sdxl'), variant='fp16',
            torch_dtype=torch.float16, use_safetensors=True, local_files_only=True, add_watermarker=False)
    pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_tiling()
    pipe.set_progress_bar_config(disable=True)
    jobs = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    for job in jobs:
        prompt = (job['prompt'] + ', high-end editorial photography for a corporate annual report, '
                  + job.get('color_name', 'neutral') + ' used sparingly, tactile materials, '
                  'natural architectural light, sophisticated composition, no text')
        image = pipe(prompt=prompt, negative_prompt='text, watermark, logo, letters, hands, fingers, bad anatomy, blurry, low quality, cartoon, neon glow, hologram, generic circuit pattern, dashboard interface',
                     width=1024, height=1024, num_inference_steps=20, guidance_scale=6).images[0]
        image.save(job['output'])
