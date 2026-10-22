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


if __name__ == "__main__":
    unittest.main()
