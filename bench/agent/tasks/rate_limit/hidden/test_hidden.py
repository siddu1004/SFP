import importlib
import threading
import unittest

import payments


def req(client="a"):
    return {"client": client, "path": "/charge", "amount": 100}


class Hidden(unittest.TestCase):
    def setUp(self):
        importlib.reload(payments)   # a fresh limiter for every test

    def test_five_pass_sixth_is_429(self):
        codes = [payments.handle(req(), now=1000 + i)["status"] for i in range(6)]
        self.assertEqual(codes, [200] * 5 + [429])

    def test_clients_are_separate(self):
        for i in range(5):
            payments.handle(req("a"), now=1000 + i)
        self.assertEqual(payments.handle(req("b"), now=1005)["status"], 200)

    def test_window_rolls(self):
        for i in range(5):
            payments.handle(req(), now=1000 + i)
        self.assertEqual(payments.handle(req(), now=1059)["status"], 429)
        self.assertEqual(payments.handle(req(), now=1060.5)["status"], 200)

    def test_retry_after(self):
        for i in range(5):
            payments.handle(req(), now=1000 + i)
        r = payments.handle(req(), now=1030)
        self.assertEqual(r["status"], 429)
        value = {k.lower(): v for k, v in r["headers"].items()}.get("retry-after")
        self.assertIsInstance(value, str)
        self.assertEqual(int(value), 30)

    def test_thread_safe(self):
        results = []
        def go():
            results.append(payments.handle(req("t"), now=5000)["status"])
        threads = [threading.Thread(target=go) for _ in range(64)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(200), 5)

    def test_other_paths_unchanged(self):
        self.assertEqual(payments.handle({"client": "a", "path": "/x"}, now=1)["status"], 404)
