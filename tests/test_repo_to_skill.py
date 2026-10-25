import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import scripts.repo_to_skill as rts


class TestRepoToSkill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.tmp, "sample-repo")
        os.makedirs(self.repo_dir)
        with open(os.path.join(self.repo_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write("# SampleUI\nA modern React UI library with accessible components and animations.")
        with open(os.path.join(self.repo_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write('{"name": "sample-ui", "version": "1.0.0"}')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_infer_category_frontend(self):
        context, readme = rts.extract_context(self.repo_dir)
        cat = rts.infer_category("sample-ui", context)
        self.assertEqual(cat, "frontend")

    def test_infer_category_custom(self):
        context, readme = rts.extract_context(self.repo_dir)
        cat = rts.infer_category("sample-ui", context, custom="my-custom-cat")
        self.assertEqual(cat, "my-custom-cat")

    def test_distill_markdown_structure(self):
        context, readme = rts.extract_context(self.repo_dir)
        md = rts.distill_markdown("sample-ui", "frontend", context, readme)
        self.assertTrue(md.startswith("---"))
        self.assertIn("name: sample-ui", md)
        self.assertIn("description:", md)
        self.assertIn("# sample-ui", md)
        self.assertIn("## When to Use", md)

    def test_convert_pipeline(self):
        dest = os.path.join(self.tmp, "dest_skill")
        mock_cat_file = os.path.join(self.tmp, "categories.json")
        with open(mock_cat_file, "w", encoding="utf-8") as f:
            json.dump({"categories": {"frontend": "UI"}, "names": {}}, f)

        res = rts.convert(self.repo_dir, custom_category="frontend", dest=dest, categories_file=mock_cat_file)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["skill_name"], "sample-repo")
        self.assertTrue(os.path.isfile(res["skill_path"]))
        with open(res["skill_path"], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("name: sample-repo", content)


if __name__ == "__main__":
    unittest.main()
