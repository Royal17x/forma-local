"""Friendly Windows launcher for Forma."""
import os
import socket
import tkinter as tk
from tkinter import messagebox
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def service_ready():
    try:
        with socket.create_connection(('127.0.0.1', 11434), timeout=1.5):
            return True
    except OSError:
        return False


def main():
    notices = []
    sdxl_ready = (ROOT / 'models/sdxl/READY').exists() or \
        (ROOT / 'models/sdxl/unet/diffusion_pytorch_model.fp16.safetensors').exists()
    if not sdxl_ready:
        notices.append('Модель изображений SDXL ещё не установлена. Можно продолжить без иллюстраций.')
    if not service_ready():
        notices.append('Ollama не запущена. Запустите Ollama, затем создайте презентацию.')
    if notices:
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning('Forma — подготовка', '\n\n'.join(notices))
        root.destroy()
    os.chdir(ROOT)
    import desktop
    desktop.api = desktop.API()
    desktop.api._window = desktop.webview.create_window(
        'Forma — локальные презентации',
        html=(ROOT / 'studio/index.html').read_text(encoding='utf-8'),
        js_api=desktop.api, width=1380, height=900, min_size=(1060, 720),
        background_color='#F4F4EF')
    desktop.api._window.events.closing += lambda: desktop.api._engine.stop()
    desktop.webview.start(gui='edgechromium', private_mode=True, debug=False)


if __name__ == '__main__':
    main()
