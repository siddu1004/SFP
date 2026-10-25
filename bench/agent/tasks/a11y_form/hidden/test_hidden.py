import unittest
from html.parser import HTMLParser


class Doc(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []          # (tag, attrs, inside_label)
        self.label_depth = 0
        self.headings = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or '') for k, v in attrs}
        self.tags.append((tag, a, self.label_depth > 0))
        if tag == 'label':
            self.label_depth += 1
        if tag in ('h1', 'h2'):
            self.headings += 1

    def handle_endtag(self, tag):
        if tag == 'label' and self.label_depth:
            self.label_depth -= 1


def load():
    d = Doc()
    with open('signup.html', encoding='utf-8') as f:
        d.feed(f.read())
    return d


def inputs(d):
    return {a.get('id'): (a, inside) for t, a, inside in d.tags if t == 'input' and a.get('type', 'text') not in ('submit', 'hidden')}


class Hidden(unittest.TestCase):
    def setUp(self):
        self.d = load()

    def test_page_language(self):
        self.assertTrue(any(t == 'html' and a.get('lang') for t, a, _ in self.d.tags))

    def test_every_field_has_a_label(self):
        fors = {a.get('for') for t, a, _ in self.d.tags if t == 'label'}
        for i, (a, inside) in inputs(self.d).items():
            self.assertTrue(i in fors or inside or a.get('aria-label') or a.get('aria-labelledby'), i)

    def test_real_submit_button(self):
        self.assertTrue(any((t == 'button' and a.get('type', 'submit') == 'submit') or (t == 'input' and a.get('type') == 'submit')
                            for t, a, _ in self.d.tags))
        self.assertFalse(any(t == 'div' and 'onclick' in a for t, a, _ in self.d.tags))

    def test_field_types(self):
        f = inputs(self.d)
        self.assertEqual(f['email'][0].get('type'), 'email')
        self.assertEqual(f['password'][0].get('type'), 'password')

    def test_required_fields(self):
        for i, (a, _) in inputs(self.d).items():
            self.assertTrue('required' in a or a.get('aria-required') == 'true', i)

    def test_error_is_announced(self):
        # Any error message counts if screen readers hear it: a live region or alert, or one linked to its field.
        with open('signup.html', encoding='utf-8') as f:
            source = f.read()
        announced = any(a.get('role') in ('alert', 'status') or a.get('aria-live') for _, a, _ in self.d.tags) or \
            "'role', 'alert'" in source or '"role", "alert"' in source or 'aria-live' in source
        described = any(a.get('aria-describedby') for a, _ in inputs(self.d).values())
        self.assertTrue(announced or described)

    def test_autocomplete(self):
        f = inputs(self.d)
        self.assertTrue(f['email'][0].get('autocomplete'))
        self.assertTrue(f['password'][0].get('autocomplete'))
        self.assertTrue(f['name'][0].get('autocomplete'))

    def test_heading(self):
        self.assertGreaterEqual(self.d.headings, 1)
