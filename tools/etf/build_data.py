#!/usr/bin/env python3
"""Assemble ../../etf_data.js (loaded by tase-etfs.html) for the INVESCO and iShares funds listed on TASE.

INVESCO inputs  : tase_funds.json (TASE facts) · holdings_raw.json (invesco.com exposures) · aum.json
iShares inputs  : ishares_map.json (ids) · tase_ishares.json (TASE facts) · ishares_raw.json (ishares.com)
Shared inputs   : fund_text_he.json (Hebrew names/descriptions/translations) · fund_meta.json (hand-curated
                  category, region, comparison groups) · prices.json (update_prices.py, fully automatic)

Returns are PRICE returns of the TASE-listed unit in ILS (close-to-close); the price feed carries no
distribution adjustment. A full-year return needs a close on or before 31 Dec of the previous year;
otherwise it is withheld (the fund was not held at the start of the year). In a fund's listing year the
partial return since listing is kept, flagged as partial, for the information list only.
"""
import datetime, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "etf_data.js")
load = lambda n: json.load(open(os.path.join(HERE, n), encoding="utf-8"))

text, meta, prices = load("fund_text_he.json"), load("fund_meta.json"), load("prices.json")
inv_tase, inv_raw, inv_aum = load("tase_funds.json")["funds"], load("holdings_raw.json")["funds"], load("aum.json")
ish_map, ish_tase, ish_raw = load("ishares_map.json")["funds"], load("tase_ishares.json")["funds"], load("ishares_raw.json")["funds"]

# Fund size is used to ORDER the lists. Two INVESCO funds and one iShares fund are quoted in EUR, so for the
# ordering they are converted at an approximate rate; the displayed figure stays in the source currency.
EURUSD_FOR_SORT = 1.15
MAX_GAP_DAYS = 14        # a year-end price older than this (illiquid fund) is not accepted as the year-end price
REGISTRATION_GAP_DAYS = 90   # some funds show one registration quote years before real trading starts
UNLISTED_FIRST_TRADE = "2026-11-04"          # iShares energy / semiconductors / India: first trading day (TASE history page)

def fmt_aum(ccy, v):
    sym = {"USD": "$", "EUR": "€"}[ccy]
    if v >= 1e9: return "%s%.2fB" % (sym, v / 1e9)
    return "%s%.0fM" % (sym, v / 1e6) if v >= 1e8 else "%s%.2fM" % (sym, v / 1e6)

def parse_inv_aum(txt):
    m = re.match(r"([$€])([0-9.,]+)([MB])$", txt)
    v = float(m.group(2).replace(",", "")) * (1e9 if m.group(3) == "B" else 1e6)
    return ("USD" if m.group(1) == "$" else "EUR"), v

CUR = re.compile(r"(?:IUSD|AUSD|USD|JPY|KRW|HKD|CNY|TWD)\s*[0-9.]*\s*(?:NPV)?$")
def clean(name):
    n = CUR.sub("", name.strip()).strip()
    n = re.sub(r"\s+(NPV|ORD)$", "", n).strip()
    return n or name

def pairs(s):
    return [(a.rsplit("|", 1)[0], float(a.rsplit("|", 1)[1])) for a in s.split(";")] if s else []

missing = set()
def tr(dic, k):
    if k in dic: return dic[k]
    missing.add(k); return k

def last_on_or_before(rows, date, max_gap=None):
    v = None
    for r in rows:
        if r[0] <= date: v = r
        else: break
    if v and max_gap is not None and (datetime.date.fromisoformat(date) - datetime.date.fromisoformat(v[0])).days > max_gap:
        return "stale"
    return v

asof = max(rows[-1][0] for rows in prices.values())
cur_year = int(asof[:4])

def build(mgr, sec, ticker, fact, name_en, ccy_aum, aum_v, raw, extra):
    t = text["funds"][sec]
    d = {"mgr": mgr, "sec": sec, "ticker": ticker, "name": t["name"], "nameEn": name_en, "desc": t["desc"],
         "fee": fact["fee"], "ccy": fact["ccy"], "ref": fact["ref"],
         "aum": fmt_aum(ccy_aum, aum_v), "aumUsd": aum_v * (EURUSD_FOR_SORT if ccy_aum == "EUR" else 1)}
    d.update({k: v for k, v in meta["funds"][sec].items()})
    rows = prices.get(ticker) if ticker else None
    if rows:
        listed = rows[0][0]
        if len(rows) > 1 and (datetime.date.fromisoformat(rows[1][0]) - datetime.date.fromisoformat(rows[0][0])).days > REGISTRATION_GAP_DAYS:
            rows = rows[1:]                      # lone registration quote; real trading starts at the next row
            d["listed"] = listed
        first, last = rows[0], rows[-1]
        d["firstTrade"], d["lastDate"], d["lastPrice"] = first[0], last[0], last[1]
        d["stale"] = (datetime.date.fromisoformat(asof) - datetime.date.fromisoformat(last[0])).days > 5
        if abs(last[2] - last[1]) / last[1] > 1e-4 and False: pass
        if fact.get("last") and abs(fact["last"] - last[1]) / fact["last"] > 0.005:
            print("WARNING price mismatch vs TASE page:", sec, fact["last"], last[1])
        rets = {}
        for y in range(first[0] and int(first[0][:4]), cur_year + 1):
            start = last_on_or_before(rows, "%d-12-31" % (y - 1), MAX_GAP_DAYS)
            end = last_on_or_before(rows, "%d-12-31" % y, MAX_GAP_DAYS) if y < cur_year else last
            if end is None or (end != "stale" and end[0] < "%d-01-01" % y):
                rets[y] = {"r": None, "why": "none"}
            elif start == "stale" or end == "stale":
                rets[y] = {"r": None, "why": "illiquid"}
                print("withheld (no price within %d days of year end): %s %s %s" % (MAX_GAP_DAYS, sec, ticker, y))
            elif start is None:
                rets[y] = {"r": None, "why": "listed", "partial": round((end[1] / first[1] - 1) * 100, 2), "from": first[0], "to": end[0]}
            else:
                rets[y] = {"r": round((end[1] / start[1] - 1) * 100, 2), "from": start[0], "to": end[0]}
        d["returns"] = {str(y): v for y, v in rets.items()}
        d["adjDiffers"] = any(abs(c - a) / c > 1e-4 for _, c, a in rows)
    else:                                       # listed so recently that no price history exists yet
        d["firstTrade"] = UNLISTED_FIRST_TRADE
        d["lastDate"], d["lastPrice"], d["stale"] = None, fact.get("last"), False
        d["returns"], d["adjDiffers"] = {}, False
    d.update(extra(raw))
    return d

def inv_extra(h):
    e = {"isin": h["isin"]}
    if h.get("country"): e["country"] = [[tr(text["countries"], n), w, n] for n, w in pairs(h["country"])]
    if h.get("sector"):  e["sector"] = [[tr(text["sectors"], n), w, n] for n, w in pairs(h["sector"])]
    if h.get("top10"):   e["top10"] = [[clean(n), w] for n, w in pairs(h["top10"])]
    if h.get("creditQuality"):
        e["credit"] = [[tr(text["ratings"], n), w] for n, w in pairs(h["creditQuality"])]
        e["rating"] = [[n, w] for n, w in pairs(h["rating"])]
    return e

def ish_extra(h):
    e = {}
    if h.get("geography"): e["country"] = [[tr(text["countries"], n), w, n] for n, w in pairs(h["geography"])]
    if h.get("sector"):    e["sector"] = [[tr(text["sectors"], n), w, n] for n, w in pairs(h["sector"])]
    if h.get("top10"):     e["top10"] = [[clean(n), w] for n, w in pairs(h["top10"])]
    return e

funds = []
for f in inv_tase:
    ccy, v = parse_inv_aum(inv_aum["aum"][f["sec"]])
    funds.append(build("INVESCO", f["sec"], f["ticker"], f, f["fullName"], ccy, v, inv_raw[f["sec"]], inv_extra))
for m in ish_map:
    r = ish_raw[m["pid"]]
    ccy, v = r["aum"]
    d = build("iShares", m["sec"], m["ticker"], ish_tase[m["sec"]], r["title"], ccy, v, r, ish_extra)
    d["pid"] = m["pid"]
    funds.append(d)

funds.sort(key=lambda d: -d["aumUsd"])           # biggest fund first, everywhere
years = sorted({int(y) for f in funds for y, v in f["returns"].items() if v["r"] is not None})

data = {"aumAsOf": "2026-11-05", "generated": datetime.date.today().isoformat(), "pricesAsOf": asof,
        "years": years, "groups": meta["groups"], "groupNotes": meta["groupNotes"], "funds": funds}
open(OUT, "w", encoding="utf-8").write(
    "/* generated by tools/etf/build_data.py - do not edit by hand */\n"
    "window.ETF_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
print("wrote", os.path.normpath(OUT), os.path.getsize(OUT), "bytes;", len(funds), "funds;", "years", years, "prices as of", asof)
if missing: print("WARNING untranslated names:", sorted(missing))
if any(f["adjDiffers"] for f in funds): print("NOTE: some funds now carry adjusted closes - review the 'price return' wording")
for f in funds:
    if f["stale"]: print("stale price:", f["mgr"], f["ticker"], "last trade", f["lastDate"])
