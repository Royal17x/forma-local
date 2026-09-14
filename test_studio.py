import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from studio.core import Engine, validate_slide, local_post, rules_for, compact_sentence, normalize_primary, color_name, chart_from_source, attach_source_chart, prepare_web_query, fetch_web_context, validate_project_for_export, select_source_excerpt

SLIDE = {'title':'Заголовок', 'summary':'Краткое объяснение.', 'points':[
    {'heading':'Первое', 'body':'Объяснение.'}, {'heading':'Второе', 'body':'Объяснение.'}],
    'notes':'Заметки', 'missing_data':[], 'image_prompt':'Editorial still life'}

class StudioTests(unittest.TestCase):
    def test_large_source_selects_relevant_piece_within_budget(self):
        source = ('Первый раздел. ' * 1000) + '\n\nКибербезопасность продукта: проверка доступа и аудит.'
        excerpt = select_source_excerpt(source, 'Кибербезопасность продукта', 1200)
        self.assertLessEqual(len(excerpt), 1200)
        self.assertIn('Кибербезопасность продукта', excerpt)

    def test_user_image_replaces_only_selected_slide_without_model(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / 'test-project').mkdir()
            source = folder / 'picture.jpg'
            Image.new('RGB', (640, 480), '#297d71').save(source)
            engine = Engine()
            engine.project = {'id': 'test-project', 'context': {'topic': 'Test'},
                              'slides': [{**copy.deepcopy(SLIDE), 'layout': 'focus'},
                                         {**copy.deepcopy(SLIDE), 'layout': 'columns'}],
                              'render': 'existing'}
            with patch('studio.core.PROJECTS', folder), \
                 patch.object(engine, 'begin', side_effect=lambda work: work()), \
                 patch.object(engine, 'render') as render, \
                 patch('studio.core.ask') as model:
                engine.import_image(1, source)
            result = render.call_args.args[0]
            self.assertEqual(result['slides'][0]['layout'], 'focus')
            self.assertEqual(result['slides'][1]['layout'], 'editorial')
            self.assertEqual(result['slides'][1]['image_origin'], 'user')
            self.assertTrue((folder / 'test-project' / result['slides'][1]['image']).exists())
            model.assert_not_called()
    def test_export_preflight_accepts_native_visuals_and_https_sources(self):
        project={'id':'missing-project', 'slides':[{**copy.deepcopy(SLIDE),
            'chart':{'type':'line','categories':['2022','2023','2024'],'values':[1,2,3]},
            'sources':['https://example.org/fact']}]}
        self.assertTrue(validate_project_for_export(project))

    def test_export_preflight_rejects_broken_source_link(self):
        project={'id':'missing-project', 'slides':[{**copy.deepcopy(SLIDE), 'sources':['http://example.org']}]}
        with self.assertRaises(ValueError):
            validate_project_for_export(project)

    def test_web_query_contains_only_topic_and_is_explicit(self):
        query=prepare_web_query('Риски контроля ИИ', 'ru')
        self.assertIn('Риски контроля ИИ', query)
        self.assertIn('2026', query)
        self.assertNotIn('секретный текст', query)

    def test_web_parser_keeps_public_result_urls_and_snippets(self):
        html='<a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.org%2Ffact">Fact</a>' \
             '<a class="result__snippet">Official fact</a>'
        with patch('studio.core.requests.Session') as factory:
            session=factory.return_value.__enter__.return_value
            session.get.return_value.text=html
            result=fetch_web_context('test query')
        self.assertEqual(result, [{'url':'https://example.org/fact','snippet':'Official fact'}])

    def test_line_chart_uses_explicit_ordered_years(self):
        chart=chart_from_source('2022: 12%; 2023: 18%; 2024: 15%')
        self.assertEqual(chart, {'type':'line','categories':['2022','2023','2024'],
                                 'values':[12.0,18.0,15.0],'unit':'%'})
        self.assertEqual(chart_from_source('Январь: 4; Февраль: 7; Март: 6')['type'], 'line')

    def test_bar_chart_uses_explicit_categories(self):
        chart=chart_from_source('Север: 12; Юг: 18; Запад: 15')
        self.assertEqual(chart['type'],'bar')
        self.assertEqual(chart['values'],[12.0,18.0,15.0])

    def test_ambiguous_or_missing_series_is_skipped(self):
        self.assertIsNone(chart_from_source('В 2022 году выручка выросла на 18%'))
        self.assertIsNone(chart_from_source('2024: 12; 2022: 18; 2023: 15'))
        self.assertIsNone(chart_from_source('А: 12%; Б: 18; В: 15%'))
        self.assertIsNone(chart_from_source('А: 12; Б: 18'))

    def test_chart_replaces_one_slide_without_extra_image(self):
        slides=[{**copy.deepcopy(SLIDE),'layout':'editorial'} for _ in range(10)]
        project={'context':{'source':'А: 12; Б: 18; В: 15'},'slides':slides}
        self.assertTrue(attach_source_chart(project))
        charts=[slide for slide in slides if slide['layout']=='chart']
        self.assertEqual(len(charts),1)
        self.assertEqual(charts[0]['chart']['type'],'bar')
        self.assertTrue(attach_source_chart(project))
        self.assertEqual(sum(bool(slide.get('chart')) for slide in slides),1)

    def test_auto_visual_accepts_model_selected_pie(self):
        from studio.core import attach_auto_visual
        slides=[{**copy.deepcopy(SLIDE),'layout':'editorial'} for _ in range(5)]
        slides[2]['summary']='Доли: 20, 30 и 50.'
        project={'context':{'source':'Доли: 20, 30 и 50.'},'slides':slides}
        proposal={'kind':'pie','slide_index':2,'title':'Доли','categories':['A','B','C'],
                  'values':[20,30,50],'unit':'%','nodes':[],'edges':[]}
        with patch('studio.core.ask',return_value=proposal):
            self.assertTrue(attach_auto_visual(project))
        self.assertEqual(project['slides'][2]['chart']['type'],'pie')

    def test_auto_visual_rejects_unobserved_numbers(self):
        from studio.core import attach_auto_visual
        slides=[{**copy.deepcopy(SLIDE),'layout':'editorial'} for _ in range(5)]
        project={'context':{'source':'Описание без чисел.'},'slides':slides}
        proposal={'kind':'bar','slide_index':2,'title':'Показатель','categories':['A','B','C'],
                  'values':[20,30,50],'unit':'','nodes':[],'edges':[]}
        with patch('studio.core.ask',return_value=proposal):
            self.assertFalse(attach_auto_visual(project))

    def test_primary_color_is_validated_and_described(self):
        self.assertEqual(normalize_primary('#2450a4'), '#2450A4')
        self.assertEqual(color_name('#2450a4'), 'blue')
        with self.assertRaises(ValueError):
            normalize_primary('blue; http://example.com')
    def test_compact_sentence_keeps_complete_claim(self):
        text = 'Первое утверждение закончено. ' + 'Второе утверждение очень длинное. '*10
        self.assertEqual(compact_sentence(text, 40), 'Первое утверждение закончено.')
    def test_ai_rules_do_not_leak_into_unrelated_topics(self):
        self.assertNotIn('AGI', rules_for({'topic':'Коммерческое предложение по логистике'}))
        self.assertIn('AGI', rules_for({'topic':'Риски контроля ИИ'}))
    def test_reject_overflow(self):
        item=copy.deepcopy(SLIDE)
        item['points'][0]['body']='a'*241
        with self.assertRaises(ValueError): validate_slide(item)

    def test_reject_invalid_points(self):
        item=copy.deepcopy(SLIDE)
        item['points']=['invalid', 'invalid']
        with self.assertRaises(ValueError): validate_slide(item)

    def test_network_is_loopback_without_proxy_or_redirect(self):
        with patch('studio.core.requests.Session') as factory:
            session=factory.return_value.__enter__.return_value
            local_post({'model':'qwen3:8b'})
            args,kwargs=session.post.call_args
            self.assertEqual(args[0], 'http://127.0.0.1:11434/api/generate')
            self.assertFalse(kwargs['allow_redirects'])
            self.assertFalse(session.trust_env)

    def test_concurrent_generation_rejected(self):
        engine=Engine()
        engine.lock.acquire()
        self.assertIn('error',engine.generate({}))
        engine.lock.release()

    def test_image_only_keeps_text(self):
        engine=Engine()
        engine.project={'id':'test','context':{},'slides':[copy.deepcopy(SLIDE)]}
        engine.project['slides'][0]['layout']='columns'
        original=copy.deepcopy(engine.project['slides'][0])
        with patch.object(engine,'begin',side_effect=lambda f:f()),patch.object(engine,'images'),patch.object(engine,'render') as render,patch('studio.core.generate_slide',return_value={**SLIDE,'image_prompt':'New image'}):
            engine.regenerate(0,'image','New image')
        updated=render.call_args.args[0]['slides'][0]
        for key in ['title','summary','points','notes','missing_data']:
            self.assertEqual(updated[key],original[key])
        self.assertEqual(updated['image_prompt'],'New image')
        self.assertEqual(engine.project['slides'][0], original)

    def test_text_only_keeps_image(self):
        engine=Engine()
        old={**copy.deepcopy(SLIDE),'image':'original.png','layout':'editorial'}
        engine.project={'id':'test','context':{},'slides':[old]}
        replacement={**copy.deepcopy(SLIDE),'title':'Новый текст','image_prompt':'Changed prompt'}
        with patch.object(engine,'begin',side_effect=lambda f:f()),patch.object(engine,'images') as images,patch.object(engine,'render') as render,patch('studio.core.generate_slide',return_value=replacement):
            engine.regenerate(0,'text','Перепиши')
        updated=render.call_args.args[0]['slides'][0]
        self.assertEqual(updated['image'],'original.png')
        self.assertEqual(updated['image_prompt'],old['image_prompt'])
        self.assertEqual(updated['title'],'Новый текст')
        images.assert_not_called()

    def test_numeric_fabrication_is_rejected(self):
        from studio.core import generate_slide
        bad={**copy.deepcopy(SLIDE),'summary':'Выручка выросла на 70%'}
        with patch('studio.core.ask',return_value=bad):
            result=generate_slide({'source':'Данных о выручке нет'},'Отчёт')
        self.assertNotIn('70%', json.dumps(result, ensure_ascii=False))
        self.assertEqual(len(result['points']), 2)

    def test_model_failure_returns_safe_slide_instead_of_stopping(self):
        from studio.core import generate_slide
        with patch('studio.core.ask', side_effect=RuntimeError('temporary model response error')):
            result=generate_slide({'source':'','language':'ru'},'Слайд о проверке')
        self.assertEqual(len(result['points']), 2)
        self.assertTrue(result['title'])

if __name__=='__main__': unittest.main()
