"""Verify that plain/beginner task sets do not trivially leak skill name tokens into task prompts."""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
    'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were',
    'will', 'with', 'my', 'our', 'this', 'we', 'how', 'do', 'i', 'can', 'cant',
    'get', 'help', 'me', 'without', 'when', 'into', 'what', 'you', 'your', 'so',
    'make', 'show', 'give', 'need', 'want', 'like', 'some', 'any', 'all'
}


def tokenize(text):
    return {w for w in re.findall(r'[a-zA-Z0-9]+', text.lower()) if len(w) > 2 and w not in STOPWORDS}


class TaskSetsTest(unittest.TestCase):
    def check_leakage(self, filepath, max_allowed_ratio=0.25):
        self.assertTrue(os.path.isfile(filepath), f"Missing task set: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            cases = json.load(f)
        leaked_count = 0
        total = len(cases)
        for c in cases:
            task_tokens = tokenize(c['task'])
            # Extract non-stopword tokens from all expected skill names
            skill_tokens = set()
            for s in c.get('expect', []):
                for part in s.split('-'):
                    part_toks = tokenize(part)
                    skill_tokens.update(part_toks)
            overlap = task_tokens & skill_tokens
            if overlap:
                leaked_count += 1
        leak_ratio = leaked_count / total
        self.assertLessEqual(
            leak_ratio, max_allowed_ratio,
            f"{os.path.basename(filepath)} has {leak_ratio:.1%} ({leaked_count}/{total}) tasks sharing tokens with skill names (max allowed {max_allowed_ratio:.0%})"
        )

    def test_plain_tuning_leakage(self):
        self.check_leakage(os.path.join(ROOT, 'tests', 'plain_tuning.json'), max_allowed_ratio=0.25)


if __name__ == '__main__':
    unittest.main()
