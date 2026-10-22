# Labeling products with an AI chat

The keyword rules in `categories.py` miss products with unusual names (a wine called "Vila Annone",
a toy set called "Hestestald og rideskole"). An AI chat is good at those. This is the copy-and-paste loop.
Needs Python on your PC (check with `python --version`; on Windows `py` also works).

## Every time you scrape

1. **Scrape.** In a terminal in the project folder:

   ```
   python fetch_offers.py
   ```

   At the end it writes the prompt files and tells you how many products have no label yet:
   `labeling\prompt_1.txt`, `prompt_2.txt` and so on (300 products each).

2. **Ask the AI.** Open `labeling\prompt_1.txt`, copy everything, and paste it into ChatGPT (or another chat).
   It answers with one short line per product, like `12|koed|hakket oksekød`.
   Repeat for `prompt_2.txt` and the rest, in a new message each time.
   If the chat stops early, write "continue" and copy the whole answer anyway.

3. **Give the answer to the script.** Either:

   - save the replies in `labeling\answer.txt` (paste them one after another into the same file), or
   - run `python labels.py apply --paste`, paste the answer, then type `END` and press Enter.

4. **Apply.**

   ```
   python labels.py apply
   ```

   It saves the labels, shows which products changed category compared to the keyword rules, and writes
   the full list to `labeling\report.txt`. Look it over. The ids are numbers from the prompt, so the
   answer must keep them as given.

5. **Update the page.** Push the changes in GitHub Desktop. The labels live in
   `site\data\category_overrides.json`, and the site's update applies them on top of the keyword rules.
   Not happy with the result? In GitHub Desktop, right-click that file and choose *Discard changes*
   before you push.

## Good to know

- A product is only labeled once, by name. Next time only new products show up in the prompt.
- Products the AI skipped, or gave an unknown category, are asked about again in the next prompt.
  `python labels.py prompt` makes new prompt files without scraping again.
- `python labels.py prompt --all` includes products that already have a label, to check them again.
- Besides the category, the AI gives each product a generic **type** (for example "pasta" for both spaghetti
  and penne). The site's search also looks at the type, so searching "pasta" finds all of them.
- The `labeling` folder is only your working space and is not uploaded to GitHub.
