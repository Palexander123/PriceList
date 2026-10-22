import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import labels  # noqa: E402
from categories import category_list  # noqa: E402

CATS = category_list()
LOOKUP = labels.lookup_table(CATS)


class ParseAnswer(unittest.TestCase):
    def test_two_and_three_digit_ids_keep_their_number(self):
        got = labels.parse_answer("12|koed|pasta\n105|drikke|vin\n1|fisk|laks")
        self.assertEqual(got, {12: ["koed", "pasta"], 105: ["drikke", "vin"], 1: ["fisk", "laks"]})

    def test_messy_reply(self):
        reply = """Her er dine labels:
```
1|koed|hakket oksekød
- 2|Frugt & grønt|banan
3 | drikke | mælk
| 4 | mejeri | letmælk |
|---|---|---|
| id | category | type |
5;kolonial;pasta
```
Sig til hvis du vil have mere!"""
        got = labels.parse_answer(reply)
        self.assertEqual(sorted(got), [1, 2, 3, 4, 5])
        self.assertEqual(got[3], ["drikke", "mælk"])
        self.assertEqual(got[4], ["mejeri", "letmælk"])

    def test_resolve_names_labels_and_extra_title_column(self):
        self.assertEqual(labels.resolve(["koed", "Hakket Oksekød"], LOOKUP), ("koed", "hakket oksekød", ""))
        self.assertEqual(labels.resolve(["Frugt & grønt", "banan"], LOOKUP)[0], "groent")
        self.assertEqual(labels.resolve(["Kød", "bøf"], LOOKUP)[0], "koed")
        # "id|title|category|type"
        self.assertEqual(labels.resolve(["Barilla spaghetti", "kolonial", "pasta"], LOOKUP), ("kolonial", "pasta", ""))
        self.assertEqual(labels.resolve(["mad", "noget"], LOOKUP)[0], None)


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "site" / "data").mkdir(parents=True)
        self.titles = [f"Vare nummer {i}" for i in range(1, 8)] + ["Vila Annone", "vila   annone"]
        self.offers = [{"title": t, "category": "andet", "price": 10} for t in self.titles]
        doc = {"meta": {}, "chains": [], "categories": CATS, "offers": self.offers}
        (self.root / "site" / "data" / "offers.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_prompts_have_global_ids_and_skip_labelled_products(self):
        n, files = labels.write_prompts(self.root, self.offers, {}, CATS, size=3)
        self.assertEqual(n, 8)                       # duplicate "vila annone" counts once
        self.assertEqual(len(files), 3)
        second = files[1].read_text(encoding="utf-8")
        self.assertIn("\n4|Vare nummer 4\n", second)  # part 2 continues at 4
        self.assertIn("koed = meat and cold cuts", second)
        n2, _ = labels.write_prompts(self.root, self.offers, {"vila annone": {"c": "drikke", "t": ""}}, CATS)
        self.assertEqual(n2, 7)

    def test_apply_saves_labels_updates_offers_and_reports(self):
        labels.write_prompts(self.root, self.offers, {}, CATS, size=100)
        reply = "1|koed|hakket oksekød\n2|mad|noget\n8|drikke|rødvin\n99|koed|ghost\n"
        r = labels.apply_answers(self.root, [reply])
        self.assertEqual(r["saved"], 2)
        self.assertEqual([t for t, _ in r["bad"]], ["Vare nummer 2"])
        self.assertEqual(r["stray"], [99])
        self.assertEqual(len(r["unanswered"]), 5)
        saved = json.loads((self.root / "site" / "data" / "category_overrides.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["items"]["vila annone"], {"c": "drikke", "t": "rødvin"})
        doc = json.loads((self.root / "site" / "data" / "offers.json").read_text(encoding="utf-8"))
        wine = [o for o in doc["offers"] if "annone" in o["title"].lower()]
        self.assertTrue(all(o["category"] == "drikke" and o["type"] == "rødvin" for o in wine))
        self.assertTrue((self.root / "labeling" / "report.txt").exists())

    def test_second_round_keeps_earlier_labels(self):
        labels.write_prompts(self.root, self.offers, {}, CATS, size=100)
        labels.apply_answers(self.root, ["1|koed|bøf"])
        labels.write_prompts(self.root, self.offers, {"vare nummer 1": {"c": "koed", "t": "bøf"}}, CATS, size=100)
        labels.apply_answers(self.root, ["1|fisk|laks"])      # id 1 is now another product
        saved = json.loads((self.root / "site" / "data" / "category_overrides.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["items"]["vare nummer 1"]["c"], "koed")
        self.assertEqual(len(saved["items"]), 2)


if __name__ == "__main__":
    unittest.main()
