"""The mentor and understanding loop (mcp/sfp_mentor.py, mcp/sfp_learn.py):
intent recording, unmet needs identification, and research topic prioritization.

Run: python -m unittest discover -s tests -v
"""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['SFP_ROOT'] = ROOT
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_intent
import sfp_learn as learn
import sfp_mcp as core
import sfp_mentor as mentor


class FakeChatServer(http.server.BaseHTTPRequestHandler):
    chat_answer = 'Autonomous Agent Security\nAdvanced RAG Evaluation'
    last_prompt = ''

    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
        FakeChatServer.last_prompt = body.get('messages', [{}])[-1].get('content', '')
        resp = {
            'choices': [{
                'message': {
                    'role': 'assistant',
                    'content': FakeChatServer.chat_answer
                }
            }]
        }
        data = json.dumps(resp).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class MentorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='sfp-mentor-test-')
        self.saved_data = os.environ.get('SFP_DATA_DIR')
        os.environ['SFP_DATA_DIR'] = self.tmp

    def tearDown(self):
        if self.saved_data is not None:
            os.environ['SFP_DATA_DIR'] = self.saved_data
        else:
            os.environ.pop('SFP_DATA_DIR', None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_decision_record_stores_top_3_meaning_matches_and_gap_flag_without_task_text(self):
        import sfp_embed
        orig_enabled = sfp_embed.enabled
        orig_similar = sfp_embed.similar
        try:
            sfp_embed.enabled = lambda: True
            sfp_embed.similar = lambda q, k=3: [(0.82, 'python-testing'), (0.71, 'tdd-workflow'), (0.59, 'pytest-expert')]
            
            res = learn.decide('run pytest suite on payment checkout')
            self.assertIsNotNone(res['decision'])
            
            with open(os.path.join(self.tmp, 'decisions.jsonl'), 'r', encoding='utf-8') as f:
                row = json.loads(f.readline())
            
            # Meaning and gap must be stored
            self.assertIn('meaning', row)
            self.assertIn('gap', row)
            self.assertEqual(len(row['meaning']), 3)
            self.assertEqual(row['meaning'][0], [0.82, 'python-testing'])
            self.assertIsInstance(row['gap'], bool)
            
            # Privacy: task text and paths must NOT be stored
            serialized = json.dumps(row)
            self.assertNotIn('payment checkout', serialized)
            self.assertNotIn('run pytest suite', serialized)
        finally:
            sfp_embed.enabled = orig_enabled
            sfp_embed.similar = orig_similar

    def test_mentor_profile_identifies_unmet_needs_grouped_by_category(self):
        now = time.time()
        # Seed decisions.jsonl with two unmet needs: one with gap=True, one with weak meaning (< 0.64)
        decisions = [
            # Decision 1: gap=True, closest skill in security
            {
                'id': 'd_1', 't': now - 100, 'v': 3, 'engine': 'select-3.18.0',
                'tech': ['python'], 'phases': {'test': 1.0}, 'stack': ['python-testing'],
                'cand': {}, 'words': ['security', 'scan'],
                'meaning': [[0.75, 'security-scan'], [0.60, 'penetration-testing-with-strix']],
                'gap': True
            },
            # Decision 2: weak closest meaning (0.52 < 0.64), closest skill in frontend
            {
                'id': 'd_2', 't': now - 50, 'v': 3, 'engine': 'select-3.18.0',
                'tech': ['react'], 'phases': {'design': 1.0}, 'stack': ['high-end-visual-design'],
                'cand': {}, 'words': ['3d', 'webgl'],
                'meaning': [[0.52, 'high-end-visual-design']],
                'gap': False
            },
            # Decision 3: satisfied decision (gap=False, strong meaning 0.85)
            {
                'id': 'd_3', 't': now - 10, 'v': 3, 'engine': 'select-3.18.0',
                'tech': ['python'], 'phases': {'test': 1.0}, 'stack': ['python-testing'],
                'cand': {}, 'words': ['test', 'unit'],
                'meaning': [[0.85, 'python-testing']],
                'gap': False
            }
        ]
        with open(os.path.join(self.tmp, 'decisions.jsonl'), 'w', encoding='utf-8') as f:
            for d in decisions:
                f.write(json.dumps(d) + '\n')

        prof = mentor.profile(now=now)
        self.assertIn('unmet_needs', prof)
        self.assertIn('unmet', prof)
        
        unmet_cats = [u['name'] for u in prof['unmet_needs']]
        expected_security = core.SKILLS['security-scan']['category']
        expected_frontend = core.SKILLS['high-end-visual-design']['category']
        self.assertIn(expected_security, unmet_cats)
        self.assertIn(expected_frontend, unmet_cats)

    def test_topics_for_prioritizes_unmet_needs_over_interests_with_fake_llm(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeChatServer)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        port = server.server_address[1]
        ep = {'model': 'fake-coder', 'runtime': 'LM Studio', 'base_url': f'http://127.0.0.1:{port}/v1'}

        prof = {
            'categories': [{'name': 'testing-quality', 'weight': 10.0}],
            'skills': [{'name': 'tdd-workflow', 'weight': 10.0}],
            'tech': [{'name': 'python', 'weight': 5.0}],
            'gaps': [],
            'unmet_needs': [{'name': 'security', 'weight': 12.0}],
            'evidence': {'decisions': 5, 'feedback': 2, 'activity': 0}
        }

        try:
            topics = mentor.topics_for(prof, n=2, ep=ep)
            self.assertEqual(len(topics), 2)
            self.assertEqual(topics[0], 'Autonomous Agent Security')
            self.assertEqual(topics[1], 'Advanced RAG Evaluation')
            
            # Verify the prompt passed to the model presented unmet needs with highest priority
            prompt = FakeChatServer.last_prompt
            self.assertIn('unmet needs', prompt.lower())
            self.assertIn('highest priority', prompt.lower())
            self.assertIn('security', prompt.lower())
        finally:
            server.shutdown()
            server.server_close()

    def test_topics_for_fallback_ranks_unmet_needs_first_when_model_unavailable(self):
        orig_find = sfp_intent.find_model
        try:
            sfp_intent.find_model = lambda: None
            prof = {
                'categories': [{'name': 'testing-quality', 'weight': 10.0}, {'name': 'backend', 'weight': 8.0}],
                'skills': [],
                'tech': [],
                'gaps': [],
                'unmet_needs': [{'name': 'security', 'weight': 15.0}],
                'evidence': {}
            }
            topics = mentor.topics_for(prof, n=3, ep=None)
            self.assertEqual(topics[0], 'security')
            self.assertEqual(topics[1], 'testing quality')
            self.assertEqual(topics[2], 'backend')
        finally:
            sfp_intent.find_model = orig_find


if __name__ == '__main__':
    unittest.main()
