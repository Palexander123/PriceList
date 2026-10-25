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

    def test_everything_on_one_line(self):
        got = labels.parse_answer("1|drikke|rødvin 2|kolonial|tomat 3|mejeri|revet ost 10|koed|pølser")
        self.assertEqual(got, {1: ["drikke", "rødvin"], 2: ["kolonial", "tomat"],
                               3: ["mejeri", "revet ost"], 10: ["koed", "pølser"]})

    def test_tags_are_read(self):
        cat, typ, tags, bad = labels.parse_fields(["drikke", "Sodavand", "sodavand, Læskedrik / kondi", "kondi"], LOOKUP)
        self.assertEqual((cat, typ, bad), ("drikke", "sodavand", ""))
        self.assertEqual(tags, ["sodavand", "læskedrik", "kondi"])
        self.assertEqual(labels.parse_fields(["koed", "bøf"], LOOKUP)[2], [])
        self.assertEqual(labels.parse_fields(["Færdigretter", "lasagne"], LOOKUP)[0], "faerdigret")
        self.assertEqual(labels.parse_fields(["Vin", "rødvin"], LOOKUP)[0], "vin")

    def test_tags_outside_the_fixed_list_are_dropped(self):
        vocab = {"sodavand", "drikkevarer"}
        got = labels.parse_fields(["drikke", "sodavand", "Sodavand, læskedrik, drikkevarer"], LOOKUP, vocab)
        self.assertEqual(got[2], ["sodavand", "drikkevarer"])
        prompt = labels.build_prompt([(1, "Faxe Kondi", "")], CATS, ["drikkevarer", "sodavand"])
        self.assertIn("Fixed list of tags:\ndrikkevarer, sodavand", prompt)
        self.assertNotIn("Fixed list of tags", labels.build_prompt([(1, "Faxe Kondi", "")], CATS))

    def test_csv_replies(self):
        csv_text = "```csv\n1,drikke,sodavand,sodavand,læskedrik\n12,vin,rødvin,vin\n105,koed,bøf\n```"
        self.assertEqual(labels.parse_answer(csv_text), {1: ["drikke", "sodavand", "sodavand", "læskedrik"],
                                                        12: ["vin", "rødvin", "vin"], 105: ["koed", "bøf"]})
        self.assertEqual(labels.parse_answer("id,category,type,tag1\n7,groent,banan,frugt, banan"),
                         {7: ["groent", "banan", "frugt", "banan"]})                      # header ignored, spaces ok
        self.assertEqual(labels.parse_answer('3,"mejeri","skyr","skyr, mejeri"'), {3: ["mejeri", "skyr", "skyr, mejeri"]})
        one_line = "1,drikke,øl,øl,bryg 2,vin,rødvin,vin,rødvin 3,koed,bøf,ea sports fc 27, gaming"
        self.assertEqual(sorted(labels.parse_answer(one_line)), [1, 2, 3])
        cat, typ, tags, _ = labels.parse_fields(["vin", "rødvin", "vin", "rødvin", "drikkevarer"], LOOKUP)
        self.assertEqual((cat, typ, tags), ("vin", "rødvin", ["vin", "rødvin", "drikkevarer"]))
        self.assertIn("id,category,type,tag1,tag2,tag3", labels.build_prompt([(1, "Faxe Kondi", "")], CATS))

    def test_part_size_avoids_a_tiny_last_prompt(self):
        self.assertEqual(labels.part_size(900), 300)
        self.assertEqual(labels.part_size(620), 320)      # 300+300+20 would leave 20
        self.assertEqual(labels.part_size(905), 320)
        self.assertEqual(labels.part_size(350), 300)      # 300+50 is fine
        self.assertEqual(labels.part_size(620, 500), 500) # a size you typed yourself is kept


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
        self.assertIn("koed = fresh and processed meat", second)
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
        self.assertEqual(saved["items"]["vila annone"], {"c": "vin", "t": "rødvin"})
        doc = json.loads((self.root / "site" / "data" / "offers.json").read_text(encoding="utf-8"))
        wine = [o for o in doc["offers"] if "annone" in o["title"].lower()]
        self.assertTrue(all(o["category"] == "vin" and o["type"] == "rødvin" for o in wine))
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
