#!/usr/bin/env python3
"""Assemble ../../etf_data.js (loaded by tase-etfs.html) for the INVESCO and iShares funds listed on TASE.

INVESCO inputs  : tase_funds.json (TASE facts) · holdings_raw.json (invesco.com exposures) · aum.json
iShares inputs  : ishares_map.json (ids) · tase_ishares.json (TASE facts) · ishares_raw.json (ishares.com)
Shared inputs   : fund_text_he.json (Hebrew names/descriptions/translations) · fund_meta.json (hand-curated
                  category, region, comparison groups) · tase_history.json (year-end prices, listing dates,
                  read from each fund's TASE history page in a browser)

Returns are PRICE returns in ILS from TASE's adjusted close ('שער נעילה מתואם'). A full-year return needs a
traded price within MAX_GAP_DAYS of 31 Dec of BOTH the previous and the current year; a fund that was not
yet trading at the start of the year, or whose last trade was too far from the year end, gets no return.
"""
import datetime, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "etf_data.js")
load = lambda n: json.load(open(os.path.join(HERE, n), encoding="utf-8"))

text, meta, hist = load("fund_text_he.json"), load("fund_meta.json"), load("tase_history.json")["funds"]
inv_tase, inv_raw, inv_aum = load("tase_funds.json")["funds"], load("holdings_raw.json")["funds"], load("aum.json")
ish_map, ish_tase, ish_raw = load("ishares_map.json")["funds"], load("tase_ishares.json")["funds"], load("ishares_raw.json")["funds"]

# Fund size is used to ORDER the lists. Two INVESCO funds and one iShares fund are quoted in EUR, so for the
# ordering they are converted at an approximate rate; the displayed figure stays in the source currency.
EURUSD_FOR_SORT = 1.15
MAX_GAP_DAYS = 14        # a year-end price older than this (illiquid fund) is not accepted as the year-end price

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

def parse_ye(txt):
    out = {}
    for tok in (txt or "").split():
        y, rest = tok.split("=", 1)
        p = rest.split("|")
        out[int(y)] = {"date": p[0], "close": float(p[1]), "adj": float(p[2])}
    return out

TODAY_ASOF = max(d for h in hist.values() for d in [e for e in re.findall(r"\d{4}-\d{2}-\d{2}", h.get("ye", ""))] or ["2000-01-01"])
asof = TODAY_ASOF
cur_year = int(asof[:4])

def gap_days(year_end_year, date):
    return (datetime.date(year_end_year, 12, 31) - datetime.date.fromisoformat(date)).days

def build(mgr, sec, ticker, fact, name_en, ccy_aum, aum_v, raw, extra):
    t = text["funds"][sec]
    d = {"mgr": mgr, "sec": sec, "ticker": ticker, "name": t["name"], "nameEn": name_en, "desc": t["desc"],
         "fee": fact["fee"], "ccy": fact["ccy"], "ref": fact["ref"],
         "aum": fmt_aum(ccy_aum, aum_v), "aumUsd": aum_v * (EURUSD_FOR_SORT if ccy_aum == "EUR" else 1)}
    d.update(meta["funds"][sec])
    h = hist[sec]
    ye = parse_ye(h.get("ye"))
    first_year = int(h["first"][:4])
    d["firstTrade"] = h["first"]
    if ye:
        ly = max(ye); last = ye[ly]
        d["lastDate"], d["lastPrice"] = last["date"], last["close"]
        d["stale"] = (datetime.date.fromisoformat(asof) - datetime.date.fromisoformat(last["date"])).days > 5
        if fact.get("last") and abs(fact["last"] - last["close"]) / fact["last"] > 0.005:
            print("WARNING latest price differs from the TASE page:", sec, fact["last"], last["close"])
    else:
        d["lastDate"], d["lastPrice"], d["stale"] = None, fact.get("last"), False
    rets = {}
    for y in range(first_year, cur_year + 1):
        if y == first_year:
            rets[y] = {"r": None, "why": "listed"}; continue
        a, b = ye.get(y - 1), ye.get(y)
        if a is None or b is None or gap_days(y - 1, a["date"]) > MAX_GAP_DAYS or (y < cur_year and gap_days(y, b["date"]) > MAX_GAP_DAYS):
            rets[y] = {"r": None, "why": "illiquid"}
            print("withheld (no trade within %d days of the year end): %s %s %s" % (MAX_GAP_DAYS, sec, t["name"], y))
            continue
        rets[y] = {"r": round((b["adj"] / a["adj"] - 1) * 100, 2), "from": a["date"], "to": b["date"]}
    d["returns"] = {str(y): v for y, v in rets.items()}
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
for f in funds:
    if f["stale"]: print("stale price:", f["mgr"], f["name"], "last trade", f["lastDate"])
