#!/usr/bin/env python3
"""Download full daily price history (ILS agorot) for the Invesco ETFs listed on TASE.

Source: stockanalysis.com  (/api/symbol/a/TLV-IN.FFn/history?type=full&range=10Y)
 plus ?type=chart for the first trading day (the chart series starts one day earlier).
 - robots.txt allows it; we identify ourselves honestly and wait between requests.
 - 'c' = close, 'a' = close adjusted for distributions (so a/a ratios are total return).
 - Prices are in agorot (1/100 ILS); returns are ratios so the unit does not matter.
Output: prices.json  {ticker: [[YYYY-MM-DD, close, adjClose], ...]}  oldest first.
No browser is needed for this step.
"""
import datetime, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "fintools-updater/1.0 (personal use)"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)

def fetch(ticker):
    base = "https://stockanalysis.com/api/symbol/a/TLV-%s/history" % ticker
    body = get(base + "?type=full&range=10Y")["data"]
    rows = body["data"] if isinstance(body, dict) else body
    out = [[x["t"], x["c"], x.get("a", x["c"])] for x in rows if x.get("c") is not None]
    out.sort(key=lambda r: r[0])
    # the chart series carries the very first trading day, which 'full' may omit
    ch = get(base + "?type=chart")["data"]
    first = datetime.datetime.fromtimestamp(ch[0][0] / 1000, datetime.timezone.utc).date().isoformat()
    if first < out[0][0]:
        out.insert(0, [first, ch[0][1], ch[0][1] * (out[0][2] / out[0][1])])
    return out

def main():
    funds = json.load(open(os.path.join(HERE, "tase_funds.json"), encoding="utf-8"))["funds"]
    res = {}
    for f in funds:
        t = f["ticker"]
        rows = fetch(t)
        if len(rows) < 100:
            sys.exit("%s: only %d rows - refusing to continue" % (t, len(rows)))
        res[t] = rows
        print("%-9s %5d rows  %s -> %s  last close %s" % (t, len(rows), rows[0][0], rows[-1][0], rows[-1][1]))
        time.sleep(1.0)
    json.dump(res, open(os.path.join(HERE, "prices.json"), "w"), separators=(",", ":"))
    print("wrote prices.json")

if __name__ == "__main__":
    main()
