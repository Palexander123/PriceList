"""Keyword-based categorisation of Danish grocery offers.

Every category belongs to a group, which the site uses for its two filters:
  consumable  food, drink and household things you use up (toilet paper, soap, ...)
  junk        toys, electronics, meal deals (julefrokost, buffet), clothes, home and garden
  other       nothing matched; could be anything

How matching works
  * Junk rules are checked first, and only against the product title (plus a few
    hint words in the description for meal deals), so "pandekage" is never mistaken
    for "pande".
  * Food rules are checked against the title first, then title + description.
  * A keyword of 5+ letters matches anywhere in a word ("kotelet" in "svinekotelet").
  * A shorter keyword only matches at the start of a word, so "is" does not match "pris".
  * "^word" forces start-of-word matching even for long words.
  * A trailing space means the word must end there too ("^pande " matches "pande"
    but not "pandekage").

To fix a wrong category, add the keyword to the right list below.
"""
import re

CONSUMABLE, JUNK, OTHER_GROUP = "consumable", "junk", "other"

# (category id, label shown on the site, group, keywords)
JUNK_RULES = [
    ("menu", "Menuer & buffet", JUNK, [
        "julefrokost", "nytårsbuffet", "buffet", "kuvert", "catering", "^menu",
        "julemenu", "påskemenu", "selskabsmad", "forudbestil", "^brunch ", "tapasbord",
        "gaveæske", "madkasse", "mad ud af huset",
    ]),
    ("legetoej", "Legetøj & spil", JUNK, [
        "legetøj", "lego", "duplo", "playmobil", "^dukke", "puslespil", "brætspil",
        "^spil ", "^spil-", "plysdyr", "^bamse", "barbie", "hot wheels", "klodser",
        "fodbold", "sparkecykel", "skateboard", "trampolin", "pokemon", "pokémon",
        "nerf", "squishmallow", "klistermærke", "malebog", "farveblyant", "kreakasse",
        "^bold ", "gokart", "samlebilleder", "byttekort",
        "byggeri", "hovedkvarter", "rideskole", "hestestald", "legesæt", "forvandlings",
        "^mech", "ninja", "brandbil", "entreprenørmaskine", "glampinghytte", "dyrlægeklinik",
        "trailer", "vandland", "racerbil", "dragebæst", "spiderman", "spidey", "minecraft",
        "paw patrol", "peppa", "disney", "marvel", "bluey", "^tog med", "fartøj",
        "motorcykeltransporter", "affaldssorteringsvogn", "pizzeria med", "kreativt",
    ]),
    ("elektronik", "Elektronik", JUNK, [
        "^tv ", "^tv-", "fjernsyn", "høretelefon", "hovedtelefon", "earbuds",
        "ladekabel", "oplader", "powerbank", "^mobil", "smartphone", "^tablet ",
        "ipad", "iphone", "laptop", "computer", "bærbar", "^skærm", "router",
        "højtaler", "bluetooth", "^usb", "hdmi", "kamera", "smartwatch", "airfryer",
        "støvsuger", "kaffemaskine", "espressomaskine", "blender", "^mixer",
        "strygejern", "elkedel", "brødrister", "ventilator", "varmeblæser",
        "trådløs", "^led ", "^led-", "^robot", "vaffeljern", "håndmixer",
        "køkkenmaskine", "barbermaskine", "hårtørrer", "trimmer", "elektrisk",
        "^el-", "stikkontakt", "forlængerledning", "lampe", "lyskæde", "dronen",
        "gamingmus", "tastatur", "printer",
    ]),
    ("boligting", "Tøj, bolig & have", JUNK, [
        "^tøj", "sokker", "strømper", "bukser", "trøje", "jakke", "^sko ", "sengetøj",
        "håndklæde", "pyjamas", "undertøj", "t-shirt", "^hue ", "vanter", "handsker",
        "^gryde", "^pande ", "^pander ", "bestik", "^glas ", "^kop ", "^kopper ",
        "tæppe", "^pude", "^dyne", "lysestage", "julepynt", "julelys", "haveredskab",
        "^plante ", "^planter ", "^blomst", "buket", "orkidé", "krukke", "værktøj",
        "^bor ", "cykel", "^grill ", "parasol", "havemøbel", "kuffert", "rygsæk",
        "kuglepen", "skoletaske", "gardin", "^spejl", "^kasse ", "opbevaring",
        "julepapir", "gavepapir", "julekugler", "adventskrans", "juletræ",
    ]),
]

FOOD_RULES = [
    # Wine first, so that "Pinot noir" or a bottle named after a grape never lands in another list.
    ("vin", "Vin", CONSUMABLE, [
        "rødvin", "hvidvin", "rosévin", "rosé", "mousserende", "champagne", "prosecco", "^cava ",
        "^vin ", "chardonnay", "merlot", "cabernet", "sauvignon", "riesling", "rioja", "chianti",
        "pinot", "shiraz", "malbec", "primitivo", "appassimento", "ripasso", "amarone",
        "coteaux", "^vila ", "chablis", "sancerre", "bordeaux", "barolo", "portvin", "boblevin",
        "côtes", "ribera del", "tempranillo", "montepulciano", "grenache", "zinfandel",
    ]),
    # Drinks that contain a fruit or similar word ("æblejuice") must be caught before the
    # fruit rule. The category appears once in the site's list.
    ("drikke", "Drikkevarer", CONSUMABLE, [
        "juice", "smoothie", "sodavand", "energidrik", "danskvand", "lemonade", "iste",
        "kakaomælk", "booster", "cocktail", "ready to drink",
    ]),
    ("faerdigret", "Færdigretter", CONSUMABLE, [
        "færdigret", "færdigmad", "lasagne", "gryderet", "ready meal", "mikroret",
    ]),
    ("frost", "Frost", CONSUMABLE, [
        "frost", "frysevare", "isbæger", "kæmpeis", "flødeis", "pinde-is", "pizza",
        "pommes", "nuggets",
    ]),
    ("fisk", "Fisk & skaldyr", CONSUMABLE, [
        "laks", "torsk", "rejer", "sild", "makrel", "tun", "fisk", "skaldyr",
        "muslinger", "ørred", "rødspætte", "fiskefilet", "krabbe", "hummer",
    ]),
    ("koed", "Kød & pålæg", CONSUMABLE, [
        "kød", "oksekød", "svinekød", "kylling", "kalkun", "bacon", "pølse",
        "frikadelle", "medister", "kotelet", "mørbrad", "bøf", "steg", "culotte",
        "schnitzel", "pålæg", "skinke", "hakket", "flæsk", "ribbe", "leverpostej",
        "salami", "pepperoni", "bryst", "lår", "and ", "gris", "okse", "lam", "kebab",
        "spegepølse", "hotdog", "pulled",
    ]),
    ("groent", "Frugt & grønt", CONSUMABLE, [
        "æble", "pære", "banan", "appelsin", "citron", "lime", "melon", "*druer",
        "jordbær", "blåbær", "hindbær", "bær", "mango", "ananas", "avocado",
        "tomat", "agurk", "salat", "spinat", "kål", "broccoli", "blomkål",
        "gulerod", "kartof", "løg", "hvidløg", "peberfrugt", "squash", "svampe",
        "champignon", "porre", "selleri", "radise", "majs", "ærter", "bønner",
        "frugt", "grønt", "grønsag", "urter", "basilikum", "persille", "ingefær",
        "nektarin", "fersken", "blomme", "kiwi", "rødbede", "asparges",
    ]),
    ("mejeri", "Mejeri & æg", CONSUMABLE, [
        "mælk", "yoghurt", "yogurt", "skyr", "ost", "smør", "fløde", "creme fraiche",
        "æg", "kefir", "cheddar", "mozzarella", "feta", "kvark", "tykmælk",
        "minimælk", "letmælk", "kærnemælk", "lurpak", "arla", "cheasy", "hytteost",
    ]),
    ("bagning", "Brød & bagning", CONSUMABLE, [
        "*brød", "toast", "bolle", "kage", "croissant", "tebirkes",
        "wienerbrød", "mel", "sukker", "gær", "bagepulver", "vanille", "kakao",
        "bagning", "flormelis", "marcipan", "tærte", "boller", "baguette",
        "morgenbrød", "kiks", "muffin", "pandekage", "dej", "cupcake",
        "hvedemel", "bagemel", "durummel", "rugmel", "fuldkornsmel",
    ]),
    ("drikke", "Drikkevarer", CONSUMABLE, [
        "øl", "cola", "sodavand", "juice", "^vand ", "danskvand", "saft",
        "kildevand",
        "julebryg",
        "påskebryg", "kondi", "faxe", "harboe",
        "cider", "sprit", "vodka", "whisky", "gin", "rom ", "kaffe", "te ",
        "energidrik", "monster", "red bull", "tuborg", "carlsberg", "fanta",
        "sprite", "pepsi", "smoothie", "lemonade", "kakaomælk", "iste", "bouillon",
        "likør",
        "havredrik", "plantedrik", "sojadrik", "mandeldrik",
    ]),
    ("snacks", "Snacks & slik", CONSUMABLE, [
        "chips", "slik", "chokolade", "lakrids", "mentos", "tyggegummi", "vingummi", "popcorn", "nødder",
        "peanuts", "snack", "bolsjer", "karamel", "kex", "is ", "flødeboller",
        "marabou", "toms", "haribo", "nougat", "bland selv",
    ]),
    ("kolonial", "Kolonial", CONSUMABLE, [
        "pasta", "spaghetti", "ris ", "nudler", "müsli", "havre", "cornflakes",
        "morgenmad", "konserves", "dåse", "sauce", "ketchup", "sennep", "mayonnaise",
        "olie", "eddike", "krydderi", "bouillon", "suppe", "pesto", "tun ", "bønner",
        "linser", "marmelade", "honning", "nutella", "pålægschokolade", "müesli",
        "taco", "tortilla", "wok", "fond", "remoulade", "dressing", "ærter",
    ]),
    ("husholdning", "Husholdning & pleje", CONSUMABLE, [
        "vaskemiddel", "opvask", "toiletpapir", "køkkenrulle", "shampoo", "sæbe",
        "håndsæbe", "tandpasta", "tandbørste", "bleer", "affald", "pose", "rengøring",
        "skyllemiddel", "deodorant", "creme", "batteri", "lys ", "servietter",
        "vådservietter", "tampon", "bind", "barber", "hundemad", "kattemad",
        "kattegrus", "foder", "vaskepulver", "toiletrens", "alufolie", "bagepapir",
        "køkkenpapir", "plastfolie", "fryseposer", "balsam", "tandkrem", "håndcreme",
        "hårfarve", "hårspray", "plaster", "solcreme", "mundskyl",
    ]),
]

OTHER = ("andet", "Andet", OTHER_GROUP)

# One picture per category, shown on the site's filter buttons.
EMOJI = {
    "vin": "🍷", "drikke": "🥤", "faerdigret": "🍲", "frost": "🧊", "fisk": "🐟", "koed": "🥩",
    "groent": "🥦", "mejeri": "🥛", "bagning": "🍞", "snacks": "🍫", "kolonial": "🥫",
    "husholdning": "🧻", "andet": "❓", "menu": "🍽️", "legetoej": "🧸", "elektronik": "🔌",
    "boligting": "🏠",
}

# Words in the description that mark a meal deal even when the title does not.
MENU_DESCRIPTION_HINTS = ("kuvert", "bestil senest", "afhentning", "forudbestil")


def _kw_pattern(w: str) -> str:
    w = w.lower()
    explicit_start = w.startswith("^")
    anywhere = w.startswith("*")   # "*brød" also matches the end of "levebrød"
    w = w.lstrip("^*")
    end_bound = w.endswith(" ")
    core = w.strip()
    body = re.escape(core)
    if explicit_start or (len(core) < 5 and not anywhere):
        body = r"(?<![a-zæøå])" + body
    if end_bound:
        body += r"(?![a-zæøå])"
    return body


def _compile(rules):
    return [(cid, label, group, re.compile("|".join(_kw_pattern(w) for w in words)))
            for cid, label, group, words in rules]


_JUNK = _compile(JUNK_RULES)
_FOOD = _compile(FOOD_RULES)
_FOOD_NO_FROST = [r for r in _FOOD if r[0] != "frost"]
_FROZEN_DESC = re.compile(r"dybfrost|dybfrys|frosne |frostvare|frysevare|(?<![a-zæøå])frost(?![a-zæøå])")


def _match(compiled, text: str):
    t = (text or "").lower()
    for cid, _label, _group, pattern in compiled:
        if pattern.search(t):
            return cid
    return None


def classify(title: str, description: str = ""):
    """Return (category id, reason). The reason is the keyword that triggered a junk
    rule, so a wrong match is easy to find; it is None for everything else.

    Junk is judged by the title, food by the title first and the description as a
    fallback ("Kyllingebryst, frost" is meat, not frost)."""
    t = (title or "").lower()
    for cid, _label, _group, pattern in _JUNK:
        m = pattern.search(t)
        if m:
            return cid, m.group(0).strip()
    desc = (description or "").lower()
    for hint in MENU_DESCRIPTION_HINTS:
        if hint in desc:
            return "menu", f"beskrivelse: {hint}"
    # The small print often says "frost" / "tidligere frosset" for FRESH meat, so frost is only decided
    # by the title, or by clear freezer words in the description when nothing else fits.
    cat = (_match(_FOOD, title)
           or _match(_FOOD_NO_FROST, f"{title} {description}")
           or ("frost" if _FROZEN_DESC.search(desc) else None)
           or OTHER[0])
    return cat, None


def categorize(title: str, description: str = "") -> str:
    """Return just the category id."""
    return classify(title, description)[0]


def category_list():
    """Ordered [{id, label, group}] for the site's filter chips."""
    rules = FOOD_RULES + [(OTHER[0], OTHER[1], OTHER[2], [])] + JUNK_RULES
    seen, items = set(), []
    for cid, label, group, _ in rules:
        if cid not in seen:  # a category can have several rule lists
            seen.add(cid)
            items.append({"id": cid, "label": label, "group": group, "emoji": EMOJI.get(cid, "")})
    # Wine is matched first, but should be listed right after the other drinks.
    ids = [c["id"] for c in items]
    if "vin" in ids and "drikke" in ids:
        wine = items.pop(ids.index("vin"))
        items.insert([c["id"] for c in items].index("drikke") + 1, wine)
    return items


# --------------------------------------------------------------------------- #
# Using the AI's "type" to correct its category
# --------------------------------------------------------------------------- #
# The AI is more reliable about WHAT a product is (type "rødvin") than about which of our
# categories it belongs to, and old labels may predate a category (Vin, Færdigretter).
_WINE_TYPES = {
    "vin", "rødvin", "hvidvin", "rosévin", "rosé", "mousserende", "champagne", "prosecco", "cava",
    "portvin", "dessertvin", "boblevin", "sherry", "vermouth",
}
_READY_TYPES = {"gryderet", "lasagne", "wokret", "færdigmad", "vegetarret"}
_REFINABLE = {cid for cid, _l, group, _w in FOOD_RULES if group == CONSUMABLE} | {OTHER[0]}


def refine(category: str, type_: str) -> str:
    """Return the category after checking the AI's product type. Only food and drink are touched,
    so a toy called "Vinylkugle" or a menu deal is never moved."""
    if not type_ or category not in _REFINABLE:
        return category
    words = set(re.findall(r"[a-zæøåéü]+", type_.lower()))
    if words & _WINE_TYPES:
        return "vin"
    if any("færdigret" in w for w in words) or words & _READY_TYPES:
        return "faerdigret"
    if category == "frost" and "suppe" in words:      # frozen soup to heat is a ready meal
        return "faerdigret"
    return category
