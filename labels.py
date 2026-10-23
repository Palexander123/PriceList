#!/usr/bin/env python3
"""Label products with an AI chat, using copy and paste.

The flow
  1. python fetch_offers.py        scrapes the offers AND writes the prompt files
                                   (or run: python labels.py prompt)
  2. Open labeling/prompt_1.txt, copy everything, paste it into ChatGPT (or similar).
  3. Save the chat's reply as labeling/answer.txt
                                   (or run: python labels.py apply --paste, and paste it in)
  4. python labels.py apply        reads the answer, saves the labels, updates the data
  5. Push in GitHub Desktop; the site rebuilds itself.

Labels are saved in site/data/category_overrides.json, keyed by product name, so a
product is only ever labelled once. The daily update applies that file on top of the
keyword rules in categories.py.

Only the Python standard library is used.
"""
import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

import fetch_offers as fo
from categories import category_list

ROOT = Path(__file__).resolve().parent
PART_SIZE = 300

# What each category means, in the prompt that goes to the AI.
DESC = {
    "frost": "ONLY other products sold frozen from the freezer (frozen vegetables, frozen pizza, ice cream, frozen fish). Fresh or chilled meat and fish are NOT frost",
    "faerdigret": "ready meals, frozen OR chilled (lasagne, stew, wok meals, pasta dishes, soups-to-heat, prepared dishes)",
    "vin": "wine, sparkling wine, champagne, port and similar (also fortified wine)", "fisk": "fish and seafood", "koed": "meat and cold cuts",
    "groent": "fruit and vegetables", "mejeri": "dairy and eggs",
    "bagning": "bread, cakes, flour and baking",
    "drikke": "other drinks: soda, juice, beer, spirits, coffee, tea, mulled wine, plant drinks (NOT wine)",
    "snacks": "snacks, sweets and chocolate",
    "kolonial": "pantry: pasta, rice, sauces, canned goods, oil, spices, cereal",
    "husholdning": "household and personal care that gets used up (toilet paper, soap, shampoo, detergent, pet food)",
    "menu": "ready-made party menus and buffets", "legetoej": "toys and games",
    "elektronik": "electronics and appliances", "boligting": "clothing, home, garden and tools",
    "andet": "only if you truly cannot tell",
}
# Other ways a chat might write a category.
ALIASES = {
    "kød": "koed", "pålæg": "koed", "kødogpålæg": "koed", "grønt": "groent", "frugt": "groent",
    "frugtgrønt": "groent", "legetøj": "legetoej", "legetøjspil": "legetoej", "toys": "legetoej",
    "meat": "koed", "fish": "fisk", "dairy": "mejeri", "bread": "bagning", "baking": "bagning",
    "drinks": "drikke", "drink": "drikke", "pantry": "kolonial", "household": "husholdning",
    "frozen": "frost", "other": "andet", "unknown": "andet", "electronics": "elektronik",
    "home": "boligting", "færdigretter": "faerdigret", "færdigret": "faerdigret",
    "readymeals": "faerdigret", "readymeal": "faerdigret", "wine": "vin", "vine": "vin",
}


def clean(text):
    return re.sub(r"[^a-zæøå]", "", str(text or "").lower())


def lookup_table(cats):
    table = {}
    for c in cats:
        table[c["id"]] = c["id"]
        table[clean(c["label"])] = c["id"]
    for alias, cid in ALIASES.items():
        if cid in table.values():
            table[clean(alias)] = cid
    return table


def paths(root):
    return {
        "dir": root / "labeling",
        "prompts": root / "labeling" / "prompts.json",
        "offers": root / "site" / "data" / "offers.json",
        "overrides": root / "site" / "data" / "category_overrides.json",
    }


# --------------------------------------------------------------------------- #
# step 1: the prompt
# --------------------------------------------------------------------------- #
def build_prompt(items, cats):
    """items: [(id, title)]. The ids are global, so one answer file can cover every part."""
    legend = "\n".join(f"{c['id']} = {DESC.get(c['id'], c['label'])}" for c in cats)
    def line(it):
        i, t = it[0], it[1]
        d = (it[2] if len(it) > 2 else "").replace("|", "/").strip()
        return f"{i}|{t.replace('|', '/')}" + (f" :: {d}" if d else "")
    lines = "\n".join(line(it) for it in items)
    return f"""You are labelling Danish supermarket offers. For each numbered product below, reply with ONE line in this exact format:
id|category|type|tags

category must be exactly one of these ids:
{legend}

type = the generic product a shopper would search for, in lowercase Danish, singular, at most 3 words (examples: pasta, pesto, rødvin, hakket oksekød, toiletpapir, lego). Use the same word for the same kind of product, so that spaghetti and penne both get "pasta".

Some products have a hint after " :: " (the small print of the offer, for example whether it is frozen or fresh). Use it, but never repeat it in the reply.

tags = 2 to 6 broader words a shopper might type to find this kind of product, lowercase Danish, separated by commas (never use | or ; inside the tags). Be generous: include the product group and its common names and synonyms, for example cola gets "sodavand, læskedrik, drikkevarer", rugbrød gets "brød, rugbrød, pålægsbrød", a banana gets "frugt, banan".

Rules: reply with the lines only. No code block, no explanations, no header, no blank lines. One line per product, same order, do not skip any product. Keep the id numbers exactly as given (they may not start at 1). If you must stop early, stop after a complete line.

Example input:
1|Barilla spaghetti 500 g
2|Faxe Kondi 1,5 l
Example reply:
1|kolonial|pasta|pasta, spaghetti, nudler
2|drikke|sodavand|sodavand, læskedrik, drikkevarer, kondi

Products:
{lines}
"""


def write_prompts(root, offers, overrides, cats, size=PART_SIZE, include_all=False, only=None):
    """Write labeling/prompt_N.txt for every product that has no label yet.
    Returns (number of products, list of prompt files)."""
    p = paths(root)
    p["dir"].mkdir(exist_ok=True)
    for old in p["dir"].glob("prompt_*.txt"):
        old.unlink()
    titles, hints = {}, {}
    for o in offers:
        key = fo.norm_title(o["title"])
        if key in titles:
            continue
        if only:                       # only products that currently sit in these categories
            if o.get("category") not in only:
                continue
        elif not include_all and key in overrides:
            continue
        titles[key] = o["title"]
        hints[key] = " ".join((o.get("description") or "").split())[:70]
    keys = list(titles)
    meta = {"created": dt.datetime.now().isoformat(timespec="seconds"),
            "ids": {str(i + 1): k for i, k in enumerate(keys)}, "titles": titles}
    p["prompts"].write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    files = []
    for start in range(0, len(keys), size):
        chunk = [(i + 1, titles[keys[i]], hints[keys[i]]) for i in range(start, min(start + size, len(keys)))]
        f = p["dir"] / f"prompt_{start // size + 1}.txt"
        f.write_text(build_prompt(chunk, cats), encoding="utf-8")
        files.append(f)
    return len(keys), files


def announce_prompts(root, offers):
    """Called at the end of a scrape: write the prompts and say what to do next."""
    cats = category_list()
    overrides, _ = fo.load_overrides({c["id"] for c in cats}, paths(root)["overrides"])
    n, files = write_prompts(root, offers, overrides, cats)
    print()
    if not n:
        print(f"Labeling: every product already has a label ({len(overrides)} saved). Nothing to do.")
        return
    names = ", ".join(str(f.relative_to(root)) for f in files)
    print(f"Labeling: {n} products have no label yet ({len(overrides)} already saved).")
    print(f"  Prompt files: {names}")
    print("  1) Open a prompt file, copy everything, and paste it into ChatGPT (or another AI chat).")
    print("  2) Save its reply as labeling\\answer.txt  (or run: python labels.py apply --paste)")
    print("  3) Run: python labels.py apply")
    print("  4) Push in GitHub Desktop; the site updates itself.")


# --------------------------------------------------------------------------- #
# step 3: read the answer
# --------------------------------------------------------------------------- #
def parse_answer(text):
    """Return {id: [fields]}. Accepts 12|koed|pasta, bullets, code fences, markdown tables,
    spaces around the bars, and ';' or tab as separators. Anything else is ignored."""
    found = {}
    text = re.sub(r"```[A-Za-z]*", "", str(text or ""))
    pieces = []
    for raw in text.splitlines():
        # Some chats put every answer on ONE line: "1|a|b 2|c|d 3|e|f". Split before each "<digits>|".
        pieces.extend(re.split(r"\s+(?=\d+\s*\|)", raw.strip()))
    for raw in pieces:
        line = re.sub(r"^[\s\-*•>]+", "", raw)          # bullet markers, never digits
        line = re.sub(r"[\t;]", "|", line).strip().strip("|")
        fields = [f.strip() for f in line.split("|")]
        if len(fields) >= 2 and fields[0].isdigit():
            found[int(fields[0])] = fields[1:]
    return found


def clean_tags(fields):
    """Search tags from the leftover fields: split on commas, lowercase, no duplicates, at most 8."""
    tags = []
    for f in fields:
        for t in re.split(r"[,/]", f):
            t = t.strip().lower()
            if t and len(t) <= 30 and t not in tags:
                tags.append(t)
    return tags[:8]


def parse_fields(fields, lookup):
    """Find the category in the fields. Also copes with 'id|title|category|type|tags'.
    Returns (category or None, type, tags, the text that was not understood)."""
    for i in range(min(2, len(fields))):
        cat = lookup.get(clean(fields[i]))
        if cat:
            typ = fields[i + 1] if len(fields) > i + 1 else ""
            return cat, typ.lower()[:60], clean_tags(fields[i + 2:]), ""
    return None, "", [], fields[0] if fields else ""


def resolve(fields, lookup):
    """Like parse_fields, without the tags: (category or None, type, text not understood)."""
    cat, typ, _tags, bad = parse_fields(fields, lookup)
    return cat, typ, bad


def apply_answers(root, texts):
    """Merge answers into category_overrides.json and the local offers.json.
    Returns a summary dict."""
    p = paths(root)
    if not p["prompts"].exists():
        raise SystemExit("No labeling/prompts.json found. Run 'python labels.py prompt' first.")
    meta = json.loads(p["prompts"].read_text(encoding="utf-8"))
    cats = category_list()
    lookup = lookup_table(cats)
    groups = {c["id"]: c["group"] for c in cats}
    labels = {c["id"]: c["label"] for c in cats}

    found = {}
    for t in texts:
        found.update(parse_answer(t))

    offers_doc = None
    now_cat = {}
    if p["offers"].exists():
        offers_doc = json.loads(p["offers"].read_text(encoding="utf-8"))
        for o in offers_doc["offers"]:
            now_cat.setdefault(fo.norm_title(o["title"]), o["category"])

    new, bad, stray, changes = {}, [], [], []
    for pid, fields in sorted(found.items()):
        key = meta["ids"].get(str(pid))
        if not key:
            stray.append(pid)
            continue
        cat, typ, tags, badtext = parse_fields(fields, lookup)
        if not cat:
            bad.append((meta["titles"][key], badtext))
            continue
        new[key] = {"c": cat, "t": typ}
        if tags:
            new[key]["g"] = tags
        if key in now_cat and now_cat[key] != cat:
            changes.append((meta["titles"][key], now_cat[key], cat))
    unanswered = [meta["titles"][k] for i, k in meta["ids"].items() if int(i) not in found]

    items = {}
    if p["overrides"].exists():
        try:
            items = json.loads(p["overrides"].read_text(encoding="utf-8")).get("items", {})
        except (OSError, json.JSONDecodeError):
            items = {}
    items.update(new)
    if new:
        p["overrides"].parent.mkdir(parents=True, exist_ok=True)
        p["overrides"].write_text(json.dumps({"version": 1, "items": items}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        if offers_doc:   # update the local data so you can preview before pushing
            valid = {k: v for k, v in items.items() if v.get("c") in groups}
            fo.apply_overrides(offers_doc["offers"], valid, groups)
            p["offers"].write_text(json.dumps(offers_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    report = ["LABELS APPLIED", f"Saved: {len(new)} products   Total in file: {len(items)}", ""]
    report.append(f"CHANGED compared to the keyword rules ({len(changes)}):")
    report += [f"  {t}: {labels.get(a, a)} -> {labels.get(b, b)}" for t, a, b in changes]
    report += ["", f"SKIPPED, category not understood ({len(bad)}):"] + [f"  {t}  (answer said: {x!r})" for t, x in bad]
    report += ["", f"NO ANSWER ({len(unanswered)}):"] + [f"  {t}" for t in unanswered]
    if stray:
        report += ["", f"IGNORED, ids not in the prompt: {stray[:20]}"]
    if p["dir"].exists():
        (p["dir"] / "report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"saved": len(new), "total": len(items), "changes": changes, "bad": bad,
            "unanswered": unanswered, "stray": stray, "labels": labels}


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #
def read_pasted():
    print("Paste the AI's answer now, then type END on its own line and press Enter.")
    print("(If END does not work, press Ctrl+Z then Enter on Windows, or Ctrl+D on Mac/Linux.)")
    lines = []
    for line in sys.stdin:
        if line.strip() == "END":
            break
        lines.append(line)
    return "".join(lines)


def cmd_prompt(args):
    p = paths(ROOT)
    if not p["offers"].exists():
        raise SystemExit("No site/data/offers.json yet. Run 'python fetch_offers.py' first.")
    offers = json.loads(p["offers"].read_text(encoding="utf-8"))["offers"]
    cats = category_list()
    overrides, _ = fo.load_overrides({c["id"] for c in cats}, p["overrides"])
    only = {c.strip() for c in args.only.split(",") if c.strip()} or None
    n, files = write_prompts(ROOT, offers, overrides, cats, size=args.size, include_all=args.all, only=only)
    if not n:
        print("Every product already has a label. Use --all to label everything again.")
        return 0
    print(f"{n} products to label. Prompt files:")
    for f in files:
        print("  ", f.relative_to(ROOT))
    print("Paste each one into ChatGPT, save the replies in labeling\\answer.txt, then run: python labels.py apply")
    return 0


def cmd_apply(args):
    p = paths(ROOT)
    p["dir"].mkdir(exist_ok=True)
    files = sorted(p["dir"].glob("answer*.txt"))
    texts = [f.read_text(encoding="utf-8", errors="replace") for f in files]
    if args.paste or not files:
        pasted = read_pasted()
        if pasted.strip():
            texts.append(pasted)
    if not any(t.strip() for t in texts):
        print("No answer found. Save the AI's reply as labeling\\answer.txt, or use --paste.")
        return 1
    r = apply_answers(ROOT, texts)
    print(f"Saved {r['saved']} labels ({r['total']} in total).")
    if r["changes"]:
        print(f"{len(r['changes'])} differ from the keyword rules. First ones:")
        for t, a, b in r["changes"][:20]:
            print(f"   {t}: {r['labels'].get(a, a)} -> {r['labels'].get(b, b)}")
    if r["bad"]:
        print(f"{len(r['bad'])} skipped because the category was not understood, e.g. {r['bad'][0]}")
    if r["unanswered"]:
        print(f"{len(r['unanswered'])} got no answer. Run 'python labels.py prompt' to get a prompt for just those.")
    print("Full list: labeling\\report.txt")
    if r["saved"]:
        done = p["dir"] / "done"
        done.mkdir(exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        for f in files:
            shutil.move(str(f), str(done / f"{stamp}_{f.name}"))
        print("Done. Push in GitHub Desktop to update the site (or preview with: python -m http.server -d site 8000).")
    return 0 if r["saved"] else 1


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prompt", help="write prompt files for products without a label")
    pp.add_argument("--all", action="store_true", help="include products that already have a label")
    pp.add_argument("--only", default="", help="only products now in these categories, e.g. --only frost,koed")
    pp.add_argument("--size", type=int, default=PART_SIZE, help="products per prompt file (default 300)")
    pa = sub.add_parser("apply", help="read the AI's answer and save the labels")
    pa.add_argument("--paste", action="store_true", help="paste the answer into the terminal")
    args = ap.parse_args(argv)
    return {"prompt": cmd_prompt, "apply": cmd_apply}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
