#!/usr/bin/env python3
"""Fetch grocery offers for Netto, Føtex and SuperBrugsen and write one JSON file
that the static site reads.

Sources
  1. Tjek (eTilbudsavis) public offers API - the weekly leaflet offers, all chains.
  2. Salling Group Food Waste API - clearance items in Netto/Føtex near a zip code.
     Needs a free key in the SALLING_API_KEY environment variable (or a .env file).
     Skipped with a note if the key is missing.

Usage
  python fetch_offers.py                 # fetch live data -> site/data/offers.json
  python fetch_offers.py --sample        # build from tests/fixtures (no network)

Only the Python standard library is used.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from categories import EXTRA_FALLBACK, EXTRA_IDS, category_list, classify, extras, extras_from_type, refine

ROOT = Path(__file__).resolve().parent
TJEK_BASE = "https://squid-api.tjek.com/v2"
SALLING_BASE = "https://api.sallinggroup.com/v1"
USER_AGENT = "grocery-deals-personal/1.0 (private hobby project, low request rate)"
PAGE_SIZE = 100
MAX_PAGES = 15  # hard stop so a bug can never loop forever


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_dotenv(path: Path) -> None:
    """Tiny .env reader so you do not need python-dotenv."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_json(url: str, headers=None, retries: int = 3, pause: float = 1.5):
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    req_headers.update(headers or {})
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code} for {url.split('?')[0]}"
            if e.code in (401, 403, 404):  # retrying will not help
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = f"{type(e).__name__}: {e}"
        time.sleep(pause * attempt)
    raise RuntimeError(last_error or "unknown error")


def parse_iso(value):
    """Tjek uses '2026-10-23T21:59:59+0000'; normalise to UTC ISO or None."""
    if not value:
        return None
    try:
        v = value.replace("Z", "+00:00")
        if len(v) > 5 and v[-5] in "+-" and v[-3] != ":":
            v = v[:-2] + ":" + v[-2:]
        return dt.datetime.fromisoformat(v).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def pct_off(price, pre_price):
    if price is not None and pre_price and pre_price > price > 0:
        return round((1 - price / pre_price) * 100)
    return None


def unit_price(price, quantity):
    """Price per kg / l when the quantity is unambiguous, else None."""
    try:
        unit = (quantity or {}).get("unit") or {}
        si = unit.get("si") or {}
        symbol, factor = si.get("symbol"), num(si.get("factor"))
        size, pieces = quantity.get("size") or {}, quantity.get("pieces") or {}
        s_from, s_to = num(size.get("from")), num(size.get("to"))
        p_from, p_to = num(pieces.get("from")) or 1, num(pieces.get("to")) or 1
        if symbol not in ("kg", "l") or not factor or not s_from or s_from != s_to or p_from != p_to:
            return None
        total = s_from * factor * p_from
        if total <= 0 or price is None:
            return None
        return {"value": round(price / total, 2), "per": symbol}
    except (AttributeError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Tjek (weekly leaflet offers)
# --------------------------------------------------------------------------- #
def resolve_dealer_ids(chains: dict, pause: float) -> dict:
    """Return {chain name: dealer id}. Uses ids from config, looks up the rest by name."""
    ids = {name: c.get("dealer_id") for name, c in chains.items() if c.get("dealer_id")}
    missing = [n for n in chains if n not in ids]
    if not missing:
        return ids
    wanted = {}
    for n in missing:
        for alias in chains[n].get("match_names") or [n.lower()]:
            wanted[alias.lower()] = n
    for page in range(MAX_PAGES):
        url = f"{TJEK_BASE}/dealers?" + urllib.parse.urlencode(
            {"country_id": "DK", "limit": PAGE_SIZE, "offset": page * PAGE_SIZE})
        batch = get_json(url)
        if not batch:
            break
        for d in batch:
            chain = wanted.get((d.get("name") or "").strip().lower())
            if chain and chain not in ids:
                ids[chain] = d.get("id")
        if len(ids) == len(chains) or len(batch) < PAGE_SIZE:
            break
        time.sleep(pause)
    return ids


def normalize_tjek(o: dict, chain: str):
    pricing = o.get("pricing") or {}
    price = num(pricing.get("price"))
    title = (o.get("heading") or "").strip()
    if price is None or not title:
        return None
    pre = num(pricing.get("pre_price"))
    images = o.get("images") or {}
    dealer = o.get("dealer") or {}
    markets = dealer.get("markets") or [{}]
    slug = markets[0].get("slug") or chain
    link = None
    if o.get("catalog_id") and o.get("id"):
        link = f"https://etilbudsavis.dk/{slug}?publication={o['catalog_id']}&offer={o['id']}"
    description = (o.get("description") or "").strip()
    category, why = classify(title, description)
    ex = extras(title)
    if category == "andet" and ex:
        category = EXTRA_FALLBACK[ex[0]]
    item = {
        "id": f"tjek:{o.get('id')}",
        "chain": chain,
        "kind": "weekly",
        "store": None,
        "title": title,
        "description": description,
        "price": price,
        "was_price": pre if pre and pre > price else None,
        "discount_pct": pct_off(price, pre),
        "unit_price": unit_price(price, o.get("quantity")),
        "image": images.get("view") or images.get("thumb") or images.get("zoom"),
        "valid_from": parse_iso(o.get("run_from")),
        "valid_to": parse_iso(o.get("run_till")),
        "url": link,
        "category": category,
    }
    if why:
        item["junk_reason"] = why
    if ex:
        item["extra"] = ex
    return item


def fetch_tjek(cfg: dict):
    pause = cfg.get("request_pause_seconds", 0.6)
    loc = cfg["location"]
    ids = resolve_dealer_ids(cfg["chains"], pause)
    offers, notes = [], []
    for chain in cfg["chains"]:
        dealer_id = ids.get(chain)
        if not dealer_id:
            notes.append(f"Tjek: could not find a dealer id for {chain}")
            continue
        count = 0
        for page in range(MAX_PAGES):
            url = f"{TJEK_BASE}/offers?" + urllib.parse.urlencode({
                "dealer_ids": dealer_id,
                "r_lat": loc["lat"], "r_lng": loc["lng"], "r_radius": loc["radius_m"],
                "limit": PAGE_SIZE, "offset": page * PAGE_SIZE,
            })
            batch = get_json(url)
            if not isinstance(batch, list):
                raise RuntimeError(f"Tjek returned unexpected data for {chain}")
            for raw in batch:
                item = normalize_tjek(raw, chain)
                if item:
                    offers.append(item)
                    count += 1
            if len(batch) < PAGE_SIZE:
                break
            time.sleep(pause)
        notes.append(f"Tjek: {count} offers for {chain}")
        time.sleep(pause)
    return offers, notes


# --------------------------------------------------------------------------- #
# Salling Group (clearance / madspild)
# --------------------------------------------------------------------------- #
SALLING_CHAIN = {"netto": "Netto", "foetex": "Føtex", "føtex": "Føtex"}


def normalize_salling(entry: dict, store: dict):
    offer, product = entry.get("offer") or {}, entry.get("product") or {}
    title = (product.get("description") or "").strip()
    price = num(offer.get("newPrice"))
    if not title or price is None:
        return None
    brand = (store.get("brand") or "").lower()
    chain = SALLING_CHAIN.get(brand)
    if not chain:
        return None
    was = num(offer.get("originalPrice"))
    cats = product.get("categories") or {}
    cat_text = " ".join(str(v) for v in cats.values() if v)
    addr = store.get("address") or {}
    store_label = store.get("name") or chain
    if addr.get("street"):
        store_label = f"{store_label}, {addr['street']}"
    pct = num(offer.get("percentDiscount"))
    category, why = classify(title, cat_text)
    ex = extras(title)
    if category == "andet" and ex:
        category = EXTRA_FALLBACK[ex[0]]
    item = {
        "id": f"sal:{store.get('id')}:{product.get('ean') or title}",
        "chain": chain,
        "kind": "clearance",
        "store": store_label,
        "title": title,
        "description": f"Tæt på udløb. {int(offer['stock'])} tilbage." if offer.get("stock") else "Tæt på udløb.",
        "price": price,
        "was_price": was if was and was > price else None,
        "discount_pct": round(pct) if pct else pct_off(price, was),
        "unit_price": None,
        "image": product.get("image"),
        "valid_from": parse_iso(offer.get("startTime")),
        "valid_to": parse_iso(offer.get("endTime")),
        "url": None,
        "category": category,
    }
    if why:
        item["junk_reason"] = why
    if ex:
        item["extra"] = ex
    return item


def fetch_salling(cfg: dict, api_key: str):
    pause = cfg.get("request_pause_seconds", 0.6)
    allowed = set(cfg.get("salling_brands", ["netto", "foetex"]))
    offers, notes = [], []
    for zip_code in cfg.get("salling_zips", [cfg["location"]["zip"]]):
        url = f"{SALLING_BASE}/food-waste/?" + urllib.parse.urlencode({"zip": zip_code})
        stores = get_json(url, headers={"Authorization": f"Bearer {api_key}"})
        n_stores = 0
        for entry in stores if isinstance(stores, list) else []:
            store = entry.get("store") or {}
            if (store.get("brand") or "").lower() not in allowed:
                continue
            n_stores += 1
            for clearance in entry.get("clearances") or []:
                item = normalize_salling(clearance, store)
                if item:
                    offers.append(item)
        notes.append(f"Salling: {n_stores} stores in {zip_code}")
        time.sleep(pause)
    return offers, notes


# --------------------------------------------------------------------------- #
# manual / AI sorting (site/data/category_overrides.json, made with site/sorter.html)
# --------------------------------------------------------------------------- #
OVERRIDES_PATH = ROOT / "site" / "data" / "category_overrides.json"


VOCAB_PATH = ROOT / "vocabulary.txt"


def load_vocabulary(path=None):
    """The fixed list of allowed search tags (one per line), or None when there is no list."""
    try:
        text = (path or VOCAB_PATH).read_text(encoding="utf-8")
    except OSError:
        return None
    words = {ln.strip().lower() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")}
    return words or None


def norm_title(title):
    """Same normalisation as the sorter page: lowercase, single spaces."""
    return " ".join((title or "").lower().split())


def load_overrides(valid_ids, path=None):
    """Return ({normalised title: {"c": category, "t": type}}, warning or None).
    Entries with an unknown category are ignored."""
    try:
        raw = json.loads((path or OVERRIDES_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except (OSError, json.JSONDecodeError) as e:
        return {}, f"Sorting file ignored: {e}"
    items = raw.get("items", {}) if isinstance(raw, dict) else {}
    out = {}
    for key, val in items.items():
        if isinstance(val, dict) and val.get("c") in valid_ids:
            out[key] = {"c": val["c"], "t": str(val.get("t") or "").strip()[:60]}
            tags = [str(g).strip().lower()[:30] for g in (val.get("g") or []) if str(g).strip()]
            if tags:
                out[key]["g"] = tags[:8]
            xs = [x for x in (val.get("x") or []) if x in EXTRA_IDS]
            if xs:
                out[key]["x"] = xs
    return out, None


def apply_overrides(offers, overrides, groups, vocab=None):
    """Let the saved sorting win over the keyword rules. Returns how many offers changed."""
    changed = 0
    for o in offers:
        ov = overrides.get(norm_title(o["title"]))
        if not ov:
            continue
        keyword_cat = o["category"]
        cat = ov["c"]
        extra = set(o.get("extra") or []) | set(ov.get("x") or [])
        if cat in EXTRA_IDS:             # an answer that says "ready meal" or "pålæg" as its category
            extra.add(cat)
            cat = keyword_cat if keyword_cat != "andet" and keyword_cat not in EXTRA_IDS else EXTRA_FALLBACK[cat]
        elif cat == "andet" and keyword_cat != "andet":    # the AI gave up, so the keyword rules decide
            cat = keyword_cat
        cat = refine(cat, ov.get("t"), o["title"])
        o["category"] = cat
        extra |= set(extras_from_type(cat, ov.get("t")))
        if extra:
            o["extra"] = [e for e in EXTRA_IDS if e in extra]
        else:
            o.pop("extra", None)
        if ov.get("t"):
            o["type"] = ov["t"]
        tags = [g for g in ov.get("g") or [] if vocab is None or g in vocab]
        if tags:
            o["tags"] = tags
        else:
            o.pop("tags", None)
        if groups.get(cat) == "junk":
            o["junk_reason"] = "sortering"
        else:
            o.pop("junk_reason", None)
        changed += 1
    return changed


# --------------------------------------------------------------------------- #
# assembling the output
# --------------------------------------------------------------------------- #
def dedupe(offers):
    seen, out = set(), []
    for o in offers:
        if o["id"] not in seen:
            seen.add(o["id"])
            out.append(o)
    return out


def drop_expired(offers, now):
    cutoff = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return [o for o in offers if not o["valid_to"] or o["valid_to"] >= cutoff]


def build_output(offers, notes, errors, cfg, sample=False):
    now = dt.datetime.now(dt.timezone.utc)
    offers = drop_expired(dedupe(offers), now)
    offers.sort(key=lambda o: (-(o["discount_pct"] or 0), o["price"]))
    return {
        "meta": {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "location": cfg["location"]["name"],
            "sample": sample,
            "notes": notes,
            "errors": errors,
            "count": len(offers),
        },
        # a chain only gets a button if it has offers (Normal, for example, often has none)
        "chains": [{"id": k, "label": v["label"], "color": v["color"]} for k, v in cfg["chains"].items()
                   if sample or any(o["chain"] == k for o in offers)],
        "categories": category_list(),
        "offers": offers,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", action="store_true", help="build from tests/fixtures instead of the network")
    parser.add_argument("--out", default=str(ROOT / "site" / "data" / "offers.json"))
    parser.add_argument("--no-prompt", action="store_true", help="do not write the AI labeling prompt files")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):      # old Windows consoles choke on unusual characters
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    load_dotenv(ROOT / ".env")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    offers, notes, errors = [], [], []

    if args.sample:
        fx = ROOT / "tests" / "fixtures"
        tjek = json.loads((fx / "tjek_sample.json").read_text(encoding="utf-8"))
        names = {c["dealer_id"]: n for n, c in cfg["chains"].items() if c.get("dealer_id")}
        names["foetex-sample"] = "Føtex"
        for raw in tjek:
            item = normalize_tjek(raw, names.get(raw.get("dealer_id"), "Netto"))
            if item:
                offers.append(item)
        sal = json.loads((fx / "salling_sample.json").read_text(encoding="utf-8"))
        for entry in sal:
            for c in entry.get("clearances", []):
                item = normalize_salling(c, entry["store"])
                if item:
                    offers.append(item)
        notes.append("Sample data - not real offers")
    else:
        try:
            got, n = fetch_tjek(cfg)
            offers += got
            notes += n
        except RuntimeError as e:
            errors.append(f"Tjek failed: {e}")
        key = os.environ.get("SALLING_API_KEY", "").strip()
        if key:
            try:
                got, n = fetch_salling(cfg, key)
                offers += got
                notes += n
            except RuntimeError as e:
                errors.append(f"Salling failed: {e}")
        else:
            notes.append("Salling: skipped, SALLING_API_KEY is not set")

    cats = category_list()
    overrides, warning = load_overrides({c["id"] for c in cats})
    if warning:
        errors.append(warning)
    if overrides:
        n = apply_overrides(offers, overrides, {c["id"]: c["group"] for c in cats}, load_vocabulary())
        notes.append(f"Sorting: {n} offers use category_overrides.json ({len(overrides)} saved products)")

    out = build_output(offers, notes, errors, cfg, sample=args.sample)
    for line in notes + errors:
        print(line)

    if out["meta"]["count"] == 0:
        # Do not overwrite a good file with an empty one.
        print("No offers fetched - leaving existing data untouched.", file=sys.stderr)
        return 1

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {out['meta']['count']} offers to {path}")

    # On your own PC, also prepare the copy-and-paste prompt for the AI (skipped on GitHub).
    if not args.no_prompt and not os.environ.get("CI"):
        try:
            import labels
            labels.announce_prompts(ROOT, out["offers"])
        except Exception as e:  # labelling trouble must never break a scrape
            print(f"(Could not prepare the labeling prompts: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
