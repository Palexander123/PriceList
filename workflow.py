"""The logic behind the window (app.py): scrape, make prompts, apply the AI's answer, preview.

No tkinter in here, so it can be tested without a screen.
"""
import contextlib
import datetime as dt
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import fetch_offers as fo
import labels
from categories import category_list

ROOT = Path(__file__).resolve().parent
CHATGPT_URL = "https://chatgpt.com/"


class _Writer:
    """Sends everything that is print()ed to a callback (the log box in the window)."""

    def __init__(self, callback):
        self.callback = callback

    def write(self, text):
        if text:
            self.callback(text)
        return len(text or "")

    def flush(self):
        pass


def scrape(log):
    """Run the scraper. Everything it prints goes to log(text). Returns True if offers were saved."""
    with contextlib.redirect_stdout(_Writer(log)), contextlib.redirect_stderr(_Writer(log)):
        try:
            code = fo.main(["--no-prompt"])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        except Exception as e:  # show it in the window instead of crashing
            print(f"Scrape failed: {e}")
            code = 1
    return code == 0


def _offers_path(root):
    return Path(root) / "site" / "data" / "offers.json"


def category_choices():
    """[(id, label)] for the 'only these products' menu."""
    return [(c["id"], c["label"]) for c in category_list()]


def status(root=ROOT):
    """{'offers': n, 'products': n, 'labeled': n, 'unlabeled': n}, or None if there is no data yet."""
    path = _offers_path(root)
    if not path.exists():
        return None
    offers = json.loads(path.read_text(encoding="utf-8"))["offers"]
    cats = category_list()
    overrides, _ = fo.load_overrides({c["id"] for c in cats}, labels.paths(Path(root))["overrides"])
    titles = {fo.norm_title(o["title"]) for o in offers}
    labeled = sum(1 for t in titles if t in overrides)
    return {"offers": len(offers), "products": len(titles), "labeled": labeled,
            "unlabeled": len(titles) - labeled}


def make_prompts(include_all=False, size=300, root=ROOT, only=None):
    """Write labeling/prompt_N.txt. Returns the list of prompt TEXTS (empty if nothing to label)."""
    root = Path(root)
    path = _offers_path(root)
    if not path.exists():
        raise RuntimeError("There is no offer data yet. Fetch the offers first.")
    offers = json.loads(path.read_text(encoding="utf-8"))["offers"]
    cats = category_list()
    overrides, _ = fo.load_overrides({c["id"] for c in cats}, labels.paths(root)["overrides"])
    n, files = labels.write_prompts(root, offers, overrides, cats, size=max(10, int(size)),
                                    include_all=include_all, only=set(only) if only else None)
    return [f.read_text(encoding="utf-8") for f in files] if n else []


def apply_text(text, root=ROOT):
    """Save the AI's answer. Returns (result dict, summary text)."""
    root = Path(root)
    try:
        r = labels.apply_answers(root, [text])
    except SystemExit as e:
        raise RuntimeError(str(e))
    if r["saved"]:   # keep a copy of what was pasted
        done = root / "labeling" / "done"
        done.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        (done / f"{stamp}_answer.txt").write_text(text, encoding="utf-8")
    lines = [f"Saved {r['saved']} labels ({r['total']} in total)."]
    if r["changes"]:
        lines.append(f"{len(r['changes'])} products moved compared to the keyword rules. First ones:")
        for t, a, b in r["changes"][:15]:
            lines.append(f"   {t}: {r['labels'].get(a, a)} -> {r['labels'].get(b, b)}")
    if r["bad"]:
        lines.append(f"{len(r['bad'])} skipped, category not understood, e.g. {r['bad'][0]}")
    if r["unanswered"]:
        lines.append(f"{len(r['unanswered'])} got no answer. Make a new prompt to ask about just those.")
    if not r["saved"]:
        lines.append("Nothing could be read. Did you paste the AI's reply with the lines like 12|koed|pasta?")
    lines.append("The full list is in labeling\\report.txt")
    return r, "\n".join(lines)


def open_chatgpt(url=CHATGPT_URL):
    """Open ChatGPT in a private/incognito window if a known browser is found. Returns 'private' or 'normal'."""
    candidates = []
    if os.name == "nt":
        for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(key)
            if base:
                b = Path(base)
                candidates += [(b / "Google/Chrome/Application/chrome.exe", "--incognito"),
                               (b / "Microsoft/Edge/Application/msedge.exe", "--inprivate"),
                               (b / "Mozilla Firefox/firefox.exe", "-private-window")]
    else:
        for name, flag in (("google-chrome", "--incognito"), ("chromium", "--incognito"),
                           ("microsoft-edge", "--inprivate"), ("firefox", "-private-window")):
            found = shutil.which(name)
            if found:
                candidates.append((Path(found), flag))
    for exe, flag in candidates:
        if exe.exists():
            try:
                subprocess.Popen([str(exe), flag, url])
                return "private"
            except OSError:
                continue
    webbrowser.open(url)
    return "normal"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


_server = None


def start_preview(root=ROOT):
    """Serve the site folder on localhost so you can look at it before pushing. Returns the URL."""
    global _server
    if _server is None:
        handler = functools.partial(_Quiet, directory=str(Path(root) / "site"))
        for port in range(8000, 8011):
            try:
                _server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
                break
            except OSError:
                continue
        else:
            raise RuntimeError("Could not start the preview (ports 8000-8010 are busy).")
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{_server.server_address[1]}/"


def open_folder(root=ROOT):
    if os.name == "nt":
        os.startfile(str(root))  # noqa: S606 - opens the folder in Explorer
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(root)])
