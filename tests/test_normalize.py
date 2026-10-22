import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fetch_offers as fo  # noqa: E402
from categories import categorize  # noqa: E402

FX = ROOT / "tests" / "fixtures"


class Categories(unittest.TestCase):
    def test_title_decides(self):
        self.assertEqual(categorize("Kyllingebrystfilet", "Frost, 1 kg"), "koed")
        self.assertEqual(categorize("Pommes frites", "Frost, 1 kg"), "frost")

    def test_compound_words(self):
        self.assertEqual(categorize("Svinekotelet med ben"), "koed")
        self.assertEqual(categorize("Hvedemel"), "bagning")

    def test_short_keywords_do_not_match_inside_words(self):
        self.assertNotEqual(categorize("Prisen er sat ned"), "snacks")  # 'is' in 'prisen'

    def test_fallback(self):
        self.assertEqual(categorize("Zzzz qqqq"), "andet")

    def test_junk_is_detected(self):
        self.assertEqual(categorize("Den klassiske julefrokost", "Marinerede sild"), "menu")
        self.assertEqual(categorize("Mad til fest", "Pr. kuvert"), "menu")  # via description hint
        self.assertEqual(categorize("LEGO City politistation"), "legetoej")
        self.assertEqual(categorize("Hovedtelefoner trådløse"), "elektronik")
        self.assertEqual(categorize("Kaffemaskine"), "elektronik")
        self.assertEqual(categorize("Børnetrøjer 2 stk."), "boligting")

    def test_junk_reason_names_the_keyword(self):
        from categories import classify
        self.assertEqual(classify("LEGO City politistation"), ("legetoej", "lego"))
        self.assertEqual(classify("Mad til fest", "Pr. kuvert"), ("menu", "beskrivelse: kuvert"))
        self.assertEqual(classify("Hvedemel"), ("bagning", None))

    def test_real_titles_from_the_live_site(self):
        cases = {
            "Veronia Appassimento": "drikke", "ØGO økologisk æblejuice": "drikke",
            "Harboe julebryg": "drikke", "Sjov dag i vandland": "legetoej",
            "Team Spideys hovedkvarter": "legetoej", "Brunchy bacon i skiver": "koed",
            "Bagepapir i ark, Træk&Luk fryseposer": "husholdning", "Pølser 8 stk": "koed",
            "Pesto rosso": "kolonial", "Vindruer": "groent", "Schulstad levebrød": "bagning",
            "Næmt pepperoni": "koed", "Mentos": "snacks",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(categorize(title), expected)

    def test_food_is_not_mistaken_for_junk(self):
        self.assertEqual(categorize("Pandekager", "Frost"), "bagning")
        self.assertEqual(categorize("Kaffe formalet"), "drikke")
        self.assertEqual(categorize("Pærer"), "groent")
        self.assertEqual(categorize("Plantedrik"), "drikke")

    def test_household_consumables(self):
        self.assertEqual(categorize("Håndsæbe 250 ml"), "husholdning")
        self.assertEqual(categorize("Toiletpapir 16 ruller"), "husholdning")

    def test_every_category_has_a_group(self):
        from categories import category_list
        groups = {c["id"]: c["group"] for c in category_list()}
        self.assertEqual(groups["menu"], "junk")
        self.assertEqual(groups["mejeri"], "consumable")
        self.assertEqual(groups["andet"], "other")


class Helpers(unittest.TestCase):
    def test_pct_off(self):
        self.assertEqual(fo.pct_off(39, 59), 34)
        self.assertIsNone(fo.pct_off(10, None))
        self.assertIsNone(fo.pct_off(10, 10))

    def test_parse_iso_handles_tjek_offsets(self):
        self.assertEqual(fo.parse_iso("2026-10-23T21:59:59+0000"), "2026-10-23T21:59:59Z")
        self.assertEqual(fo.parse_iso("2026-10-23T23:59:59+0200"), "2026-10-23T21:59:59Z")
        self.assertIsNone(fo.parse_iso(None))

    def test_unit_price_per_kg(self):
        q = {"unit": {"symbol": "g", "si": {"symbol": "kg", "factor": 0.001}},
             "size": {"from": 500, "to": 500}, "pieces": {"from": 1, "to": 1}}
        self.assertEqual(fo.unit_price(32, q), {"value": 64.0, "per": "kg"})

    def test_unit_price_skips_ranges(self):
        q = {"unit": {"symbol": "cl", "si": {"symbol": "l", "factor": 0.01}},
             "size": {"from": 25, "to": 50}, "pieces": {"from": 8, "to": 24}}
        self.assertIsNone(fo.unit_price(79, q))


class Normalisation(unittest.TestCase):
    def test_tjek_sample(self):
        raw = json.loads((FX / "tjek_sample.json").read_text(encoding="utf-8"))
        items = [fo.normalize_tjek(r, "Føtex") for r in raw]
        items = [i for i in items if i]
        self.assertEqual(len(items), len(raw))
        salmon = next(i for i in items if i["title"] == "Laks i skiver")
        self.assertEqual(salmon["discount_pct"], 34)
        self.assertEqual(salmon["category"], "fisk")
        self.assertTrue(salmon["image"])

    def test_tjek_skips_offers_without_price(self):
        self.assertIsNone(fo.normalize_tjek({"id": "x", "heading": "Gratis", "pricing": {}}, "Netto"))

    def test_salling_sample(self):
        raw = json.loads((FX / "salling_sample.json").read_text(encoding="utf-8"))
        items = [fo.normalize_salling(c, e["store"]) for e in raw for c in e["clearances"]]
        self.assertTrue(all(i and i["kind"] == "clearance" for i in items))
        self.assertEqual({i["chain"] for i in items}, {"Netto", "Føtex"})

    def test_salling_ignores_other_brands(self):
        entry = {"offer": {"newPrice": 5, "originalPrice": 10}, "product": {"description": "Noget", "ean": "1"}}
        self.assertIsNone(fo.normalize_salling(entry, {"id": "s", "brand": "bilka", "name": "Bilka"}))


class Overrides(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.old = fo.OVERRIDES_PATH
        fo.OVERRIDES_PATH = Path(self.tmp.name) / "category_overrides.json"

    def tearDown(self):
        fo.OVERRIDES_PATH = self.old
        self.tmp.cleanup()

    def test_missing_file_is_fine(self):
        self.assertEqual(fo.load_overrides({"drikke"}), ({}, None))

    def test_broken_file_is_ignored_with_a_warning(self):
        fo.OVERRIDES_PATH.write_text("{not json", encoding="utf-8")
        out, warning = fo.load_overrides({"drikke"})
        self.assertEqual(out, {})
        self.assertIn("ignored", warning)

    def test_unknown_categories_are_dropped(self):
        fo.OVERRIDES_PATH.write_text(json.dumps({"version": 1, "items": {
            "vila annone": {"c": "drikke", "t": "rødvin"}, "x": {"c": "nonsense"}}}), encoding="utf-8")
        out, _ = fo.load_overrides({"drikke"})
        self.assertEqual(out, {"vila annone": {"c": "drikke", "t": "rødvin"}})

    def test_override_beats_the_keyword_rules(self):
        offers = [{"title": "  Vila   ANNONE ", "category": "andet"},
                  {"title": "Pølser", "category": "koed", "junk_reason": "x"},
                  {"title": "Ukendt", "category": "andet"}]
        ov = {"vila annone": {"c": "drikke", "t": "rødvin"}, "pølser": {"c": "legetoej", "t": ""}}
        n = fo.apply_overrides(offers, ov, {"drikke": "consumable", "legetoej": "junk"})
        self.assertEqual(n, 2)
        self.assertEqual((offers[0]["category"], offers[0]["type"]), ("drikke", "rødvin"))
        self.assertEqual(offers[1]["junk_reason"], "sortering")
        self.assertEqual(offers[2]["category"], "andet")


if __name__ == "__main__":
    unittest.main()
