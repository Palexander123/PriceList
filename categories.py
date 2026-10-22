"""Keyword-based categorisation of Danish grocery offers.

Rules are checked top to bottom and the first match wins, so more specific
categories come first. Keywords of 5+ letters match anywhere in a word (so
"svinekotelet" matches "kotelet"); shorter ones only match at the start of a
word (so "is" does not match "pris").

To fix a wrong category, add the keyword to the right list here.
"""
import re

# (category id, label shown on the site, keywords)
RULES = [
    ("frost", "Frost", [
        "frost", "frys", "isbæger", "kæmpeis", "flødeis", "pinde-is", "pizza",
        "pommes", "nuggets",
    ]),
    ("fisk", "Fisk & skaldyr", [
        "laks", "torsk", "rejer", "sild", "makrel", "tun", "fisk", "skaldyr",
        "muslinger", "ørred", "rødspætte", "fiskefilet", "krabbe", "hummer",
    ]),
    ("koed", "Kød & pålæg", [
        "kød", "oksekød", "svinekød", "kylling", "kalkun", "bacon", "pølse",
        "frikadelle", "medister", "kotelet", "mørbrad", "bøf", "steg", "culotte",
        "schnitzel", "pålæg", "skinke", "hakket", "flæsk", "ribbe", "leverpostej",
        "salami", "bryst", "lår", "and ", "gris", "okse", "lam", "kebab",
        "spegepølse", "hotdog", "pulled",
    ]),
    ("groent", "Frugt & grønt", [
        "æble", "pære", "banan", "appelsin", "citron", "lime", "melon", "drue",
        "jordbær", "blåbær", "hindbær", "bær", "mango", "ananas", "avocado",
        "tomat", "agurk", "salat", "spinat", "kål", "broccoli", "blomkål",
        "gulerod", "kartof", "løg", "hvidløg", "peberfrugt", "squash", "svampe",
        "champignon", "porre", "selleri", "radise", "majs", "ærter", "bønner",
        "frugt", "grønt", "grønsag", "urter", "basilikum", "persille", "ingefær",
        "nektarin", "fersken", "blomme", "kiwi", "rødbede", "asparges",
    ]),
    ("mejeri", "Mejeri & æg", [
        "mælk", "yoghurt", "yogurt", "skyr", "ost", "smør", "fløde", "creme fraiche",
        "æg", "kefir", "cheddar", "mozzarella", "feta", "kvark", "tykmælk",
        "minimælk", "letmælk", "kærnemælk", "lurpak", "arla", "cheasy", "hytteost",
    ]),
    ("bagning", "Brød & bagning", [
        "brød", "rugbrød", "toast", "bolle", "kage", "croissant", "tebirkes",
        "wienerbrød", "mel", "sukker", "gær", "bagepulver", "vanille", "kakao",
        "bagning", "flormelis", "marcipan", "tærte", "boller", "baguette",
        "morgenbrød", "kiks", "muffin", "pandekage", "dej", "cupcake",
        "hvedemel", "bagemel", "durummel", "rugmel", "fuldkornsmel",
    ]),
    ("drikke", "Drikkevarer", [
        "øl", "vin", "cola", "sodavand", "juice", "vand", "danskvand", "saft",
        "cider", "sprit", "vodka", "whisky", "gin", "rom ", "kaffe", "te ",
        "energidrik", "monster", "red bull", "tuborg", "carlsberg", "fanta",
        "sprite", "pepsi", "smoothie", "lemonade", "kakaomælk", "iste", "bouillon",
        "prosecco", "champagne", "rosé", "rødvin", "hvidvin", "likør",
    ]),
    ("snacks", "Snacks & slik", [
        "chips", "slik", "chokolade", "lakrids", "vingummi", "popcorn", "nødder",
        "peanuts", "snack", "bolsjer", "karamel", "kex", "is ", "flødeboller",
        "marabou", "toms", "haribo", "nougat", "bland selv",
    ]),
    ("kolonial", "Kolonial", [
        "pasta", "spaghetti", "ris ", "nudler", "müsli", "havre", "cornflakes",
        "morgenmad", "konserves", "dåse", "sauce", "ketchup", "sennep", "mayonnaise",
        "olie", "eddike", "krydderi", "bouillon", "suppe", "pesto", "tun ", "bønner",
        "linser", "marmelade", "honning", "nutella", "pålægschokolade", "müesli",
        "taco", "tortilla", "wok", "fond", "remoulade", "dressing", "ærter",
    ]),
    ("husholdning", "Husholdning & pleje", [
        "vaskemiddel", "opvask", "toiletpapir", "køkkenrulle", "shampoo", "sæbe",
        "tandpasta", "tandbørste", "bleer", "affald", "pose", "rengøring",
        "skyllemiddel", "deodorant", "creme", "batteri", "lys ", "servietter",
        "vådservietter", "tampon", "bind", "barber", "hundemad", "kattemad",
        "kattegrus", "foder",
    ]),
]

OTHER = ("andet", "Andet")


def _compile():
    compiled = []
    for cat_id, label, words in RULES:
        patterns = []
        for w in words:
            w = w.lower()
            stripped = w.strip()
            if len(stripped) >= 5:
                # anywhere in a word: "kotelet" in "svinekotelet"
                patterns.append(re.escape(stripped))
            else:
                # short keyword: must start a word (trailing space in the
                # keyword list means the word must also end there)
                end = r"(?![a-zæøå])" if w.endswith(" ") else ""
                patterns.append(r"(?<![a-zæøå])" + re.escape(stripped) + end)
        compiled.append((cat_id, label, re.compile("|".join(patterns))))
    return compiled


_COMPILED = _compile()
LABELS = {cat_id: label for cat_id, label, _ in RULES}
LABELS[OTHER[0]] = OTHER[1]


def _match(text: str):
    t = (text or "").lower()
    for cat_id, _label, pattern in _COMPILED:
        if pattern.search(t):
            return cat_id
    return None


def categorize(title: str, description: str = "") -> str:
    """Return a category id. The title decides; the description is only a
    fallback (so "Kyllingebryst, frost" is meat, not frozen food)."""
    return _match(title) or _match(f"{title} {description}") or OTHER[0]


def category_list():
    """Ordered [{id, label}] for the site's filter chips."""
    items = [{"id": cid, "label": label} for cid, label, _ in RULES]
    items.append({"id": OTHER[0], "label": OTHER[1]})
    return items
