# Labeling products with an AI chat

The keyword rules in `categories.py` miss products with unusual names (a wine called "Vila Annone",
a toy set called "Hestestald og rideskole"). An AI chat is good at those. This is the copy-and-paste loop.
Needs Python on your PC (check with `python --version`; on Windows `py` also works).

## The easy way: one window

Double-click `Start.bat` (or run `python app.py` in Anaconda Prompt). One window with four steps:
fetch the offers, make the prompt (it is copied for you, with a button that opens ChatGPT in a
private window), paste the answer and save the labels, then preview the site. Pushing is still done
in GitHub Desktop. Everything below is the same routine done by hand with commands.

## Every time you scrape

1. **Scrape.** In a terminal in the project folder:

   ```
   python fetch_offers.py
   ```

   At the end it writes the prompt files and tells you how many products have no label yet:
   `labeling\prompt_1.txt`, `prompt_2.txt` and so on (600 products each).

2. **Ask the AI.** Open `labeling\prompt_1.txt`, copy everything, and paste it into ChatGPT (or another chat).
   It answers with one CSV row per product, in a code block, like `12,koed,hakket oksekød,kød,oksekød,hakket`.
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
- **Færdigretter** and **Pålæg** are not exclusive categories: a product keeps its normal category (a frozen lasagne is Frost) and ChatGPT adds the tag `faerdigret` or `paalaeg`. On the site they are filter buttons like the others.
- The tags can only come from the fixed list in `vocabulary.txt` (one word per line, edit it freely); any other tag is dropped. The AI also gives each product a few **tags** (broad search words like "sodavand" or "frugt"). The site's search looks at the tags, the type and the category name, so a general word finds the whole group.
- Besides the category, the AI gives each product a generic **type** (for example "pasta" for both spaghetti
  and penne). The site's search also looks at the type, so searching "pasta" finds all of them.
- The `labeling` folder is only your working space and is not uploaded to GitHub.
