"""The user's own skills (sfp_own) and the automatic research watch (sfp_research.auto).

Run:  python3 -m unittest discover -s tests -v
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_hive as hive  # noqa: E402
import sfp_mcp as core  # noqa: E402
import sfp_own as own  # noqa: E402
import sfp_research as research  # noqa: E402

FEED = ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:o="http://a9.com/-/spec/opensearch/1.1/"><o:totalResults>%d</o:totalResults></feed>')
PAPER = {'year': 2026, 'citations': 1, 'index': 'arXiv', 'abstract': 'Retrieval augmented generation evaluation in practice. ' * 8}


class OwnCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: os.environ.pop(k, None) for k in ('SFP_DATA_DIR', 'SFP_SEMANTIC', 'SFP_RESEARCH')}
        os.environ.update(SFP_DATA_DIR=self.tmp, SFP_SEMANTIC='0')

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add(self, name, does, folder=''):
        d = os.path.join(self.tmp, 'skills', folder, name)
        os.makedirs(d)
        with open(os.path.join(d, 'SKILL.md'), 'w', encoding='utf-8') as f:
            f.write('---\nname: %s\ndescription: "%s"\n---\n\n# Body\n' % (name, does))


class OwnSkillTest(OwnCase):
    def test_an_approved_skill_is_selected_and_a_draft_is_not(self):
        self.add('buck-converter-tuning', 'Tune the PI controller of a buck converter.')
        self.add('boost-converter-tuning', 'Tune the PI controller of a boost converter.', 'drafts')
        task = 'tune the PI controller of my buck converter'
        self.assertEqual([r['name'] for r in own.match(task)], ['buck-converter-tuning'])
        res = hive.select(task)
        self.assertEqual(res['yours'][0]['name'], 'buck-converter-tuning')
        self.assertEqual(res['status'], 'selected')
        self.assertIn('Your own skill: buck-converter-tuning', hive.format_stack(res))
        self.assertIn('approved by the user', core.tool_get_skill({'name': 'buck-converter-tuning'}))

    def test_one_shared_word_is_not_a_match(self):
        self.add('buck-converter-tuning', 'Tune the PI controller of a buck converter.')
        self.assertEqual(own.match('tune the postgres indexes of my shop'), [])
        self.assertEqual(own.match(''), [])
        self.assertIsNone(own.read('no-such-skill'))

    def test_badges_in_a_description_do_not_count(self):
        self.add('chips', '[](https://github.com/x/actions/workflows/ci.yml) [build](https://y) Design chips.')
        self.assertEqual(own.own()['chips']['does'], 'Design chips.')


class AutoTest(OwnCase):
    def test_it_is_off_until_turned_on_and_runs_once_per_period(self):
        ran = []
        self.assertFalse(research.start_if_due(run=ran.append))
        research.auto(True, 7)
        self.assertTrue(research.start_if_due(now=1e9, run=ran.append))
        self.assertFalse(research.start_if_due(now=1e9 + 6 * 86400, run=ran.append))
        self.assertTrue(research.start_if_due(now=1e9 + 8 * 86400, run=ran.append))
        self.assertEqual(ran[0][-2:], ['watch', '--auto'])
        os.environ['SFP_RESEARCH'] = '0'
        self.assertFalse(research.start_if_due(now=2e9, run=ran.append))

    def test_a_broken_settings_file_means_off(self):
        for bad in ('not json', '[]', '{"auto": true, "last": "x"}'):
            with open(os.path.join(self.tmp, 'research.json'), 'w') as f:
                f.write(bad)
            self.assertFalse(research.due())

    def test_trend_compares_two_periods(self):
        answers = iter([FEED % 99, FEED % 49])
        self.assertEqual(research.trend('retrieval evaluation', fetch=lambda u: next(answers)), {'recent': 99, 'before': 49, 'growth': 2.0})

        def offline(url):
            raise OSError('offline')
        self.assertEqual(research.trend('x', fetch=offline), {})

    def test_the_arxiv_query_asks_for_all_words_and_the_dates(self):
        q = research.arxiv_query('the newest practical techniques in agent skill routing', '2026-01-02')
        self.assertTrue(q.startswith('all:agent AND all:skill AND all:routing AND submittedDate:[202601020000 TO '))
        self.assertIn(datetime.date.today().strftime('%Y%m%d'), q)

    def test_without_a_loaded_model_the_papers_wait_and_are_reported(self):
        papers = [dict(PAPER, title='Retrieval paper %d' % i, url='u%d' % i) for i in range(3)]
        keep = (research.load_topics, research.trend, research.search_papers, research.make_queries, research.sfp_intent.find_model)
        research.load_topics = lambda: ['slow topic', 'retrieval evaluation', 'other']
        research.trend = lambda t, fetch=None: {'growth': 3.0 if t.startswith('retrieval') else 1.0}
        research.search_papers = lambda q, fetch=None, log=None, since=None: list(papers)
        research.make_queries = lambda t, role=None, ep=None: [t]
        research.sfp_intent.find_model = lambda **k: None
        try:
            out = research.auto_watch(log=lambda s: None)
        finally:
            research.load_topics, research.trend, research.search_papers, research.make_queries, research.sfp_intent.find_model = keep
        self.assertEqual(out[0]['topic'], 'retrieval evaluation')
        self.assertEqual(len(out[0]['papers']), 3)
        self.assertEqual(research.list_drafts(), [])
        self.assertTrue(any('3 new papers on "retrieval evaluation"' in n for n in research.news()))

    def test_papers_off_the_topic_make_no_draft(self):
        far = [dict(PAPER, title='Cooking %d' % i, url='c%d' % i, abstract='basil thyme kitchen recipes ' * 12) for i in range(3)]
        keep = (research.search_papers, research.make_queries)
        research.search_papers = lambda q, fetch=None, log=None, since=None: list(far)
        research.make_queries = lambda t, role=None, ep=None: [t]
        try:
            out = research.watch(['retrieval evaluation'], log=lambda s: None)
        finally:
            research.search_papers, research.make_queries = keep
        self.assertEqual(out, [{'topic': 'retrieval evaluation', 'new_papers': 0, 'draft': None}])


if __name__ == '__main__':
    unittest.main()
