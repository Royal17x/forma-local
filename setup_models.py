"""Explicit installation step. No presentation text is accessed by this script."""
import os
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
from pathlib import Path
from huggingface_hub import snapshot_download

if __name__ == '__main__':
    target = Path(__file__).resolve().parent / 'models/sdxl'
    snapshot_download('stabilityai/stable-diffusion-xl-base-1.0', local_dir=target,
        allow_patterns=['model_index.json', 'scheduler/*.json', 'tokenizer/*', 'tokenizer_2/*',
                        'text_encoder/config.json', 'text_encoder/*.fp16.safetensors',
                        'text_encoder_2/config.json', 'text_encoder_2/*.fp16.safetensors',
                        'unet/config.json', 'unet/*.fp16.safetensors',
                        'vae/config.json', 'vae/*.fp16.safetensors'], max_workers=2)
    (target / 'READY').write_text('SDXL base 1.0 fp16\n',encoding='utf-8')
