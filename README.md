# Tilbud i Lyngby

A small website that collects this week's offers from Netto, Føtex and SuperBrugsen near Lyngby (2800),
plus "madspild" clearance items from Netto and Føtex. Search, filter by store and category, sort by discount
or price per kg, and save favorites (kept in each visitor's own browser).

It is a static site on GitHub Pages. A GitHub Action fetches fresh offers every morning, so nothing runs on your PC.

## How it works

```
fetch_offers.py  ->  site/data/offers.json  ->  site/index.html (reads the JSON in the browser)
```

- **Weekly offers** come from Tjek (eTilbudsavis), the service behind the leaflet apps. No key needed.
- **Madspild** comes from Salling Group's food-waste API. Needs a free key (optional; without it the site still works).
- `categories.py` sorts products into meat, greens, baking and so on by keyword. Wrong category? Add the word to the right list.
- `config.json` holds the location, the chains and their colors.

## Put it online (one time, about 10 minutes)

1. **Push the folder to your GitHub repo.** In PowerShell:
   ```
   cd C:\Users\alexa\Documents\Priser
   git init -b main
   git add .
   git commit -m "First version"
   git remote add origin https://github.com/YOUR-USERNAME/grocery-deals.git
   git push -u origin main
   ```
2. **Turn on Pages:** repo → Settings → Pages → Source: **GitHub Actions**.
3. **Add your Salling key:** repo → Settings → Secrets and variables → Actions → New repository secret.
   Name `SALLING_API_KEY`, value is the key. Never paste it into a file in the repo.
4. **Run it:** repo → Actions → "Update offers and publish site" → Run workflow.
   (The first push also starts a run, but it fails until step 2 is done. Just run it again.)
5. Your site is at `https://YOUR-USERNAME.github.io/grocery-deals/`. After this it updates itself every morning.

## Try it on your PC first (optional)

You need Python 3.10 or newer.

```
copy .env.example .env        (then paste your key into .env)
python fetch_offers.py        (writes site\data\offers.json)
python -m http.server -d site 8000
```

Open http://localhost:8000. `python fetch_offers.py --sample` builds the page from fake data without using the internet.
`python -m unittest discover -s tests` runs the tests.

## Things to know

- **The Tjek endpoint is not verified by me.** My workspace could not reach it, so the code follows the response format
  I could see second-hand. The first GitHub run is the real test. If it fails, open the run's log: the error says which
  source and which request. Send me that text and I will fix it.
- **Terms.** Tjek's terms of use have not been checked. Salling's API is for private, non-commercial, small-scale use:
  one zip code and one request a day is what this does. If you want certainty about hosting it publicly, ask Salling's
  developer support.
- **Netto has no "was" price** in the leaflet data, so Netto offers have no discount percentage. Use "Laveste kilopris".
  Real discounts for Netto need price history, which is a possible next step.
- **Images** for weekly offers are crops of the leaflet page, so some show several products.
- **Favorites** live in the browser (localStorage). They do not sync between devices.
- The site is in Danish. The text is in `site/index.html` if you want to change it.
