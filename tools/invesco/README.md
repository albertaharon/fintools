# Invesco ETF page — refresh tool

Feeds `invesco-etf.html` through the generated file `../../invesco_etf_data.js`.
Everything here is public market data. Nothing personal.

## Refresh (ask Claude to run it)

| Step | What | How | How often |
|---|---|---|---|
| 1 | Daily ILS prices for the 17 funds | `python3 update_prices.py` — fully automatic, no browser | every time |
| 2 | Top-10 holdings + country/sector from invesco.com | browser step (below) → `holdings_raw.json` | monthly |
| 3 | Security numbers, fees, reference index from TASE | browser step (below) → `tase_funds.json` | only when TASE lists a new Invesco fund or a fee changes |
| 4 | Build the page data | `python3 build_data.py` | every time |

Then reload `invesco-etf.html`, check the numbers, commit and push.

`build_data.py` prints a warning for: untranslated country/sector names, funds whose price feed starts
carrying distribution adjustments (the page text says "price return" — revisit it), and stale prices
(thinly traded funds whose last trade is more than 5 days old).

## Why steps 2 and 3 use a browser

`market.tase.co.il` (Imperva) and `invesco.com` refuse scripted requests. We do not work around that.
A browser session reads the same pages a person would and the values are copied into the JSON files.
Invesco's page also blocks sending data from the page to localhost (its CSP), so the extracted
text is read from the tool output and written to the file.

### Step 3 — TASE page, one fund
Open `https://market.tase.co.il/he/market_data/security/<SEC>/major_data`, wait ~3 s, then in the console:

```js
const t=document.body.innerText, g=k=>{const m=t.match(new RegExp(k+'[^\n]*\n+\s*([^\n]+)'));return m&&m[1].trim()};
({full:g('שם קרן מלא'), ref:g('נכס ייחוס'), ccy:g('מטבע בו נקובות'),
  fee:(t.match(/דמי ניהול[^\n]*\n+\s*([0-9.]+)\s*\n/)||[])[1]})
```
The list of Invesco funds is on any of their pages (links under "לרשימת כל קרנות חוץ נסחרות למנהל", manager 2355).
When adding a fund also add its `ticker` (TASE symbol, `IN.FFn`), a Hebrew name and description in
`fund_text_he.json`, and its Invesco page slug in `holdings_raw.json`.

### Step 2 — Invesco page, one fund
Open `https://www.invesco.com/uk/en/financial-products/etfs/<slug>.html`, then scroll to "Holdings" so the
charts render and run:

```js
(async()=>{const s=ms=>new Promise(r=>setTimeout(r,ms));await s(2500);
 const h=[...document.querySelectorAll('h2,h3')].find(e=>e.innerText.trim()==='Holdings');
 if(h){h.scrollIntoView();await s(1800);for(let i=0;i<6;i++){scrollBy(0,500);await s(1200)}}
 const charts=[...document.querySelectorAll('svg.highcharts-root')].filter(x=>x.querySelector('.highcharts-pie-series'))
   .map(x=>[...x.querySelectorAll('.highcharts-point')].map(p=>p.getAttribute('aria-label').replace(/\.$/,'').replace(', ','|')).join(';'));
 const t0=document.querySelector('table');
 return {charts, cap:t0&&t0.closest('div').parentElement.innerText.slice(0,80),
   top10:t0&&[...t0.rows].slice(1).map(r=>{const c=[...r.cells].map(c=>c.innerText.trim());return c[0]+'|'+c.at(-1)}).join(';')}})()
```

Rules learned the hard way:
* **Classify charts by their content, not by position.** Swap funds list country first and sector second;
  physical funds list sector first.
* **Check the table caption.** It must say "top 10 exposures". Bond funds show "Top 10 collateral exposure",
  which is securities-lending collateral, not holdings — do not present it as holdings.
* The "Economic exposure" charts are Invesco's own look-through figures; a European index can show a
  few percent in the US. Keep them labelled as Invesco's data.
* "View all" on the page opens the full constituent list (100 rows per page) but Invesco notes that index
  components are limited by the index provider's licence, so the page shows only the top 10.

## Price source

`stockanalysis.com/api/symbol/a/TLV-IN.FFn/history` — robots.txt allows it, the request carries an honest
user agent and waits 1 s between funds. `type=full&range=10Y` returns the full daily series;
`type=chart` supplies the first trading day. Spot checks against the TASE pages matched exactly
(last close of FF1, FF14–FF17, daily change of FF1).

## Return rules

* Full-year return of year Y = close on/before 31 Dec Y-1 → close on/before 31 Dec Y
  (latest close for the current year). No prior-year close means the fund was not held at the start of
  the year: the return is withheld. In the table the listing year shows a flagged partial return.
* Returns are price returns of the TASE unit (no distribution adjustment).
