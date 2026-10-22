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
        "julemenu", "påskemenu", "selskabsmad", "forudbestil", "^brunch", "tapasbord",
        "gaveæske", "madkasse", "mad ud af huset",
    ]),
    ("legetoej", "Legetøj & spil", JUNK, [
        "legetøj", "lego", "duplo", "playmobil", "^dukke", "puslespil", "brætspil",
        "^spil ", "^spil-", "plysdyr", "^bamse", "barbie", "hot wheels", "klodser",
        "fodbold", "sparkecykel", "skateboard", "trampolin", "pokemon", "pokémon",
        "nerf", "squishmallow", "klistermærke", "malebog", "farveblyant", "kreakasse",
        "^bold ", "gokart", "samlebilleder", "byttekort",
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
    ("frost", "Frost", CONSUMABLE, [
        "frost", "frys", "isbæger", "kæmpeis", "flødeis", "pinde-is", "pizza",
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
        "salami", "bryst", "lår", "and ", "gris", "okse", "lam", "kebab",
        "spegepølse", "hotdog", "pulled",
    ]),
    ("groent", "Frugt & grønt", CONSUMABLE, [
        "æble", "pære", "banan", "appelsin", "citron", "lime", "melon", "drue",
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
        "brød", "rugbrød", "toast", "bolle", "kage", "croissant", "tebirkes",
        "wienerbrød", "mel", "sukker", "gær", "bagepulver", "vanille", "kakao",
        "bagning", "flormelis", "marcipan", "tærte", "boller", "baguette",
        "morgenbrød", "kiks", "muffin", "pandekage", "dej", "cupcake",
        "hvedemel", "bagemel", "durummel", "rugmel", "fuldkornsmel",
    ]),
    ("drikke", "Drikkevarer", CONSUMABLE, [
        "øl", "vin", "cola", "sodavand", "juice", "vand", "danskvand", "saft",
        "cider", "sprit", "vodka", "whisky", "gin", "rom ", "kaffe", "te ",
        "energidrik", "monster", "red bull", "tuborg", "carlsberg", "fanta",
        "sprite", "pepsi", "smoothie", "lemonade", "kakaomælk", "iste", "bouillon",
        "prosecco", "champagne", "rosé", "rødvin", "hvidvin", "likør",
        "havredrik", "plantedrik", "sojadrik", "mandeldrik",
    ]),
    ("snacks", "Snacks & slik", CONSUMABLE, [
        "chips", "slik", "chokolade", "lakrids", "vingummi", "popcorn", "nødder",
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

# Words in the description that mark a meal deal even when the title does not.
MENU_DESCRIPTION_HINTS = ("kuvert", "bestil senest", "afhentning", "forudbestil")


def _kw_pattern(w: str) -> str:
    w = w.lower()
    explicit_start = w.startswith("^")
    w = w.lstrip("^")
    end_bound = w.endswith(" ")
    core = w.strip()
    body = re.escape(core)
    if explicit_start or len(core) < 5:
        body = r"(?<![a-zæøå])" + body
    if end_bound:
        body += r"(?![a-zæøå])"
    return body


def _compile(rules):
    return [(cid, label, group, re.compile("|".join(_kw_pattern(w) for w in words)))
            for cid, label, group, words in rules]


_JUNK = _compile(JUNK_RULES)
_FOOD = _compile(FOOD_RULES)


def _match(compiled, text: str):
    t = (text or "").lower()
    for cid, _label, _group, pattern in compiled:
        if pattern.search(t):
            return cid
    return None


def categorize(title: str, description: str = "") -> str:
    """Return a category id. Junk is judged by the title, food by the title first
    and the description as a fallback ("Kyllingebryst, frost" is meat, not frost)."""
    hit = _match(_JUNK, title)
    if hit:
        return hit
    desc = (description or "").lower()
    if any(h in desc for h in MENU_DESCRIPTION_HINTS):
        return "menu"
    return _match(_FOOD, title) or _match(_FOOD, f"{title} {description}") or OTHER[0]


def category_list():
    """Ordered [{id, label, group}] for the site's filter chips."""
    rules = FOOD_RULES + [OTHER[:2] + (OTHER[2], [])] + JUNK_RULES
    return [{"id": cid, "label": label, "group": group} for cid, label, group, _ in rules]
