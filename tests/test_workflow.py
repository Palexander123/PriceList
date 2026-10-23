import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_offers as fo  # noqa: E402
import workflow as wf  # noqa: E402


def sample_root():
    tmp = Path(tempfile.mkdtemp())
    out = tmp / "site" / "data" / "offers.json"
    out.parent.mkdir(parents=True)
    assert fo.main(["--sample", "--out", str(out), "--no-prompt"]) == 0
    return tmp


class Workflow(unittest.TestCase):
    def test_status_without_data(self):
        self.assertIsNone(wf.status(Path(tempfile.mkdtemp())))

    def test_prompt_then_answer_in_one_line(self):
        root = sample_root()
        s = wf.status(root)
        self.assertEqual(s["labeled"], 0)
        parts = wf.make_prompts(root=root)
        self.assertEqual(len(parts), 1)
        meta = json.loads((root / "labeling" / "prompts.json").read_text(encoding="utf-8"))
        ids = sorted(int(i) for i in meta["ids"])
        answer = " ".join(f"{i}|kolonial|pasta" for i in ids)          # everything on one line
        result, summary = wf.apply_text(answer, root=root)
        self.assertEqual(result["saved"], len(ids))
        self.assertIn("Saved", summary)
        self.assertEqual(wf.status(root)["unlabeled"], 0)
        self.assertTrue(list((root / "labeling" / "done").glob("*_answer.txt")))
        self.assertEqual(wf.make_prompts(root=root), [])                # nothing left to ask
        self.assertTrue(wf.make_prompts(include_all=True, root=root))   # but can re-check all

    def test_hints_and_only_category(self):
        root = sample_root()
        offers = json.loads((root / "site" / "data" / "offers.json").read_text(encoding="utf-8"))["offers"]
        offers[0]["description"] = "Kølevare. Tidligere frosset"
        (root / "site" / "data" / "offers.json").write_text(json.dumps({"offers": offers}), encoding="utf-8")
        text = wf.make_prompts(root=root)[0]
        self.assertIn(" :: Kølevare. Tidligere frosset", text)
        cat = offers[0]["category"]
        only = wf.make_prompts(root=root, only=[cat])[0]
        body = only.split("Products:\n")[1].strip().splitlines()
        self.assertEqual(len(body), len({fo.norm_title(o["title"]) for o in offers if o["category"] == cat}))

    def test_smaller_parts(self):
        root = sample_root()
        n = wf.status(root)["products"]
        self.assertEqual(len(wf.make_prompts(size=10, root=root)), -(-n // 10))

    def test_unreadable_answer_is_reported(self):
        root = sample_root()
        wf.make_prompts(root=root)
        result, summary = wf.apply_text("sorry, I cannot help with that", root=root)
        self.assertEqual(result["saved"], 0)
        self.assertIn("Nothing could be read", summary)

    def test_apply_before_prompt_gives_clear_error(self):
        with self.assertRaises(RuntimeError):
            wf.apply_text("1|koed|x", root=sample_root())

    def test_scrape_logs_and_reports_failure(self):
        lines = []
        wf.fo.main  # exists
        orig = wf.fo.main
        wf.fo.main = lambda argv: (print("hello from scraper"), 1)[1]
        try:
            self.assertFalse(wf.scrape(lines.append))
        finally:
            wf.fo.main = orig
        self.assertIn("hello from scraper", "".join(lines))

    def test_preview_serves_the_site(self):
        import urllib.request
        root = sample_root()
        (root / "site" / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
        url = wf.start_preview(root)
        self.assertIn(b"hi", urllib.request.urlopen(url, timeout=5).read())


if __name__ == "__main__":
    unittest.main()
