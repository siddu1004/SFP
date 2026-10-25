import unittest

import users


class Hidden(unittest.TestCase):
    def setUp(self):
        self.c = users.connect()
        self.c.executemany("INSERT INTO users (name, email) VALUES (?, ?)", [
            ("Alice", "a@x.io"), ("Alan", "al@x.io"), ("Bob", "b@x.io"), ("O'Brien", "o@x.io"), ("100%_real", "r@x.io")])

    def names(self, *a, **k):
        return [u["name"] for u in users.search_users(self.c, *a, **k)]

    def test_normal_prefix(self):
        self.assertEqual(self.names("Al"), ["Alan", "Alice"])

    def test_quote_in_name(self):
        self.assertEqual(self.names("O'B"), ["O'Brien"])

    def test_injection_returns_nothing(self):
        self.assertEqual(self.names("' OR '1'='1"), [])

    def test_like_wildcards_are_literal(self):
        self.assertEqual(self.names("%"), [])
        self.assertEqual(self.names("_"), [])
        self.assertEqual(self.names("100%"), ["100%_real"])

    def test_limit_cannot_inject(self):
        try:
            self.names("A", limit="1; DROP TABLE users")
        except (ValueError, TypeError):
            pass
        self.assertEqual(self.c.execute("SELECT count(*) FROM users").fetchone()[0], 5)

    def test_limit_works(self):
        self.assertEqual(len(self.names("A", limit=1)), 1)
