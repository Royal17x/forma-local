import base64
import json
import os
import shutil
from pathlib import Path

os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
import webview
from studio.core import Engine, ROOT, PROJECTS, MODEL, prepare_web_query


class API:
    def __init__(self):
        self._engine = Engine()
        self._window = None

    def status(self):
        p = self._engine.project
        visible_project = None
        if p:
            visible_project = {**p, 'context': {k: v for k, v in p['context'].items()
                                               if k not in ('source', 'web_context')}}
        return {**self._engine.state, 'project': visible_project, 'model': MODEL,
                'image_ready': (ROOT / 'models/sdxl/unet/diffusion_pytorch_model.fp16.safetensors').exists()}

    def generate(self, data):
        return self._engine.generate(data)

    def prepare_web_query(self, data):
        topic = str(data.get('topic', '')).strip()
        language = data.get('language', 'ru')
        if not topic or len(topic) > 500 or language not in ['ru', 'en']:
            return {'error': 'Сначала укажите тему и язык презентации'}
        return {'query': prepare_web_query(topic, language)}

    def regenerate(self, index, mode, wish):
        return self._engine.regenerate(index, mode, wish)

    def import_image(self, index):
        if self._engine.state['busy']:
            return {'error': 'Дождитесь завершения текущей операции'}
        chosen = self._window.create_file_dialog(webview.FileDialog.OPEN,
            file_types=('Изображения (*.png;*.jpg;*.jpeg;*.webp)',))
        if not chosen:
            return {'cancelled': True}
        source = chosen if isinstance(chosen, str) else chosen[0]
        return self._engine.import_image(index, source)

    def stop(self):
        return self._engine.stop()

    def resume(self):
        return self._engine.resume()

    def preview(self, index):
        p = self._engine.project
        if not p or not p.get('render') or not 0 <= int(index) < len(p['slides']):
            return None
        file = PROJECTS / p['id'] / ('preview-' + p['render']) / f'{int(index)}.png'
        return 'data:image/png;base64,' + base64.b64encode(file.read_bytes()).decode()

    def projects(self):
        PROJECTS.mkdir(exist_ok=True)
        result = []
        for file in sorted(PROJECTS.glob('*/project.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                p = json.loads(file.read_text(encoding='utf-8'))
                if p.get('hidden'):
                    continue
                result.append({'id': p['id'], 'title': p['context']['topic']})
            except (ValueError, KeyError):
                pass
        return result

    def load(self, identifier):
        if self._engine.state['busy']:
            return {'error': 'Дождитесь завершения операции'}
        if identifier not in [p['id'] for p in self.projects()]:
            return {'error': 'Проект не найден'}
        self._engine.project = json.loads((PROJECTS / identifier / 'project.json').read_text(encoding='utf-8'))
        return {'ok': True}

    def export(self):
        p = self._engine.project
        if not p or not p.get('render') or self._engine.state['busy']:
            return {'error': 'Сначала дождитесь завершения сборки'}
        chosen = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename='Презентация.pptx',
                                               file_types=('PowerPoint (*.pptx)',))
        if chosen:
            target = Path(chosen if isinstance(chosen,str) else chosen[0]).with_suffix('.pptx')
            shutil.copy2(PROJECTS / p['id'] / (p['render']+'.pptx'), target)
            return {'path': str(target)}
        return {'cancelled': True}


if __name__ == '__main__':
    api = API()
    api._window = webview.create_window('Forma — локальные презентации',
        html=(ROOT/'studio/index.html').read_text(encoding='utf-8'), js_api=api,
        width=1380, height=900, min_size=(1060,720), background_color='#F4F4EF')
    api._window.events.closing += lambda: api._engine.stop()
    webview.start(gui='edgechromium', private_mode=True, debug=False)
