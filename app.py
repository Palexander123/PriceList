"""One window for the whole routine: fetch offers, get the AI prompt, paste the answer, preview.

Start it with:   python app.py      (or double-click Start.bat)
Needs nothing but Python (tkinter comes with it).
"""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import workflow as wf


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tilbud - update the discount site")
        self.geometry("860x820")
        self.minsize(720, 640)
        self.q = queue.Queue()
        self.parts = []
        self.part_i = 0
        self._build()
        self.refresh_status()
        self.after(100, self._poll)

    # ------------------------------------------------------------------ layout
    def _build(self):
        pad = {"padx": 12, "pady": 6}
        ttk.Label(self, text="Update the discount site", font=("Segoe UI", 15, "bold")).pack(anchor="w", **pad)
        self.status = ttk.Label(self, text="")
        self.status.pack(anchor="w", padx=12)

        f1 = ttk.LabelFrame(self, text="1. Fetch the offers")
        f1.pack(fill="x", **pad)
        self.btn_scrape = ttk.Button(f1, text="Fetch today's offers", command=self.do_scrape)
        self.btn_scrape.pack(side="left", padx=8, pady=8)
        ttk.Label(f1, text="Takes under a minute. Progress shows in the log below.").pack(side="left")

        f2 = ttk.LabelFrame(self, text="2. Get the prompt and ask ChatGPT")
        f2.pack(fill="x", **pad)
        row = ttk.Frame(f2)
        row.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(row, text="Ask about:").pack(side="left")
        self.choices = [("new", "New products only"), ("all", "Every product again")] + \
                       [(cid, f"Only what is now in {label}") for cid, label in wf.category_choices()]
        self.var_which = tk.StringVar(value=self.choices[0][1])
        ttk.Combobox(row, textvariable=self.var_which, state="readonly", width=34,
                     values=[label for _id, label in self.choices]).pack(side="left", padx=(4, 0))
        ttk.Label(row, text="   Products per prompt:").pack(side="left")
        self.var_size = tk.IntVar(value=300)
        ttk.Spinbox(row, from_=50, to=2000, increment=50, width=6, textvariable=self.var_size).pack(side="left")
        row = ttk.Frame(f2)
        row.pack(fill="x", padx=8, pady=6)
        ttk.Button(row, text="Make prompt", command=self.do_prompt).pack(side="left")
        ttk.Button(row, text="<", width=3, command=lambda: self.step_part(-1)).pack(side="left", padx=(12, 0))
        self.part_label = ttk.Label(row, text="no prompt yet", width=16, anchor="center")
        self.part_label.pack(side="left")
        ttk.Button(row, text=">", width=3, command=lambda: self.step_part(1)).pack(side="left")
        ttk.Button(row, text="Copy prompt again", command=self.copy_part).pack(side="left", padx=12)
        ttk.Button(row, text="Open ChatGPT (private window)", command=self.do_chatgpt).pack(side="left")
        ttk.Label(f2, text="The prompt is copied for you. Paste it into ChatGPT; for several parts, "
                           "use a new message for each.", wraplength=780).pack(anchor="w", padx=8, pady=(0, 8))

        f3 = ttk.LabelFrame(self, text="3. Paste ChatGPT's answer")
        f3.pack(fill="both", expand=True, **pad)
        self.answer = scrolledtext.ScrolledText(f3, height=7, wrap="word")
        self.answer.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        row = ttk.Frame(f3)
        row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(row, text="Paste from clipboard", command=self.do_paste).pack(side="left")
        ttk.Button(row, text="Clear", command=lambda: self.answer.delete("1.0", "end")).pack(side="left", padx=6)
        ttk.Button(row, text="Save the labels", command=self.do_apply).pack(side="left", padx=6)
        ttk.Label(row, text="(several parts: paste them one after another)").pack(side="left")

        f4 = ttk.LabelFrame(self, text="4. Look and publish")
        f4.pack(fill="x", **pad)
        row = ttk.Frame(f4)
        row.pack(fill="x", padx=8, pady=8)
        ttk.Button(row, text="Preview the site", command=self.do_preview).pack(side="left")
        ttk.Button(row, text="Open project folder", command=wf.open_folder).pack(side="left", padx=6)
        ttk.Label(row, text="Happy? Commit and push in GitHub Desktop, then run the workflow.").pack(side="left", padx=6)

        self.log_box = scrolledtext.ScrolledText(self, height=9, state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(6, 12))

    # ------------------------------------------------------------------ helpers
    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text if text.endswith("\n") else text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def refresh_status(self):
        try:
            s = wf.status()
        except Exception as e:
            self.status.config(text=f"Could not read the data: {e}")
            return
        if not s:
            self.status.config(text="No offer data yet. Start with step 1.")
        else:
            self.status.config(text=f"{s['offers']} offers, {s['products']} different products. "
                                    f"{s['labeled']} labeled, {s['unlabeled']} still without a label.")

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log(payload)
                else:
                    payload()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    # ------------------------------------------------------------------ step 1
    def do_scrape(self):
        self.btn_scrape.config(state="disabled")
        self.log("Fetching offers ...")

        def work():
            ok = wf.scrape(lambda s: self.q.put(("log", s)))
            self.q.put(("call", lambda: self._scrape_done(ok)))

        threading.Thread(target=work, daemon=True).start()

    def _scrape_done(self, ok):
        self.btn_scrape.config(state="normal")
        self.log("Done." if ok else "The fetch did not work. The old data was kept.")
        self.refresh_status()

    # ------------------------------------------------------------------ step 2
    def do_prompt(self):
        try:
            which = next((i for i, lab in self.choices if lab == self.var_which.get()), "new")
            self.parts = wf.make_prompts(include_all=(which == "all"), size=self.var_size.get(),
                                         only=None if which in ("new", "all") else [which])
        except Exception as e:
            messagebox.showerror("Prompt", str(e))
            return
        self.part_i = 0
        if not self.parts:
            self.part_label.config(text="nothing to label")
            messagebox.showinfo("Prompt", "Every product already has a label.\n"
                                          "Pick 'Every product again' (or one category) in the menu to label them again.")
            return
        self._show_part()

    def _show_part(self):
        self.part_label.config(text=f"part {self.part_i + 1} of {len(self.parts)}")
        self._copy(self.parts[self.part_i])
        self.log(f"Prompt part {self.part_i + 1} of {len(self.parts)} is copied. Paste it into ChatGPT.")

    def step_part(self, d):
        if self.parts:
            self.part_i = (self.part_i + d) % len(self.parts)
            self._show_part()

    def copy_part(self):
        if self.parts:
            self._show_part()

    def do_chatgpt(self):
        how = wf.open_chatgpt()
        self.log("Opened ChatGPT in a private window." if how == "private"
                 else "Opened ChatGPT in your browser (no private window could be started).")

    # ------------------------------------------------------------------ step 3
    def do_paste(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Paste", "The clipboard is empty.")
            return
        self.answer.insert("end", text.rstrip("\n") + "\n")

    def do_apply(self):
        text = self.answer.get("1.0", "end")
        if not text.strip():
            messagebox.showinfo("Save", "Paste ChatGPT's answer first.")
            return
        try:
            result, summary = wf.apply_text(text)
        except Exception as e:
            messagebox.showerror("Save", str(e))
            return
        self.log(summary)
        self.refresh_status()
        if result["saved"]:
            self.answer.delete("1.0", "end")
            messagebox.showinfo("Saved", summary.split("\n")[0] + "\nNext: preview, then push.")
        else:
            messagebox.showwarning("Nothing saved", summary)

    # ------------------------------------------------------------------ step 4
    def do_preview(self):
        import webbrowser
        try:
            webbrowser.open(wf.start_preview())
        except Exception as e:
            messagebox.showerror("Preview", str(e))


if __name__ == "__main__":
    App().mainloop()
