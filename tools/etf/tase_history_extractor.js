// Run in the browser console on a TASE fund history page, DESKTOP-WIDTH layout (>= ~1200px; the narrow layout
// hides the price columns and this script returns an error). Page URL pattern (custom range):
//   https://market.tase.co.il/he/market_data/security/<SEC>/historical_data/eod?pType=8&oId=0<SEC>&dFrom=2019-01-01&dTo=<today>
// It pages through the table (ngx-pagination) and prints one compact line per fund:
//   first = oldest row (listing), ye = per year 'YYYY=date|close|adjusted[|carry:date|adj]' = last day WITH A TRADE
//   on or before 31 Dec (a trade = the row has a high price), plus the official carried row when it differs.
// Paste the result into tase_history.json. For a quick mid-year refresh use dFrom=<Jan 1 of this year>: only the
// current-year entry changes. Collect the full range again each January (and after any split/unit change).
// Store once per origin to keep each call short:  sessionStorage.t = '(' + fn.toString() + ')()'  ->  eval(sessionStorage.t)
const fn = async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 40 && !document.querySelector('table tbody tr td'); i++) await sleep(250);
  await sleep(600);
  if (!/שער נעילה מתואם/.test(document.body.innerText)) return { error: 'NOCOLS (viewport too narrow)', w: innerWidth };
  const num = s => parseFloat(String(s).replace(/,/g, ''));
  const readPage = () => [...document.querySelectorAll('table tbody tr')].map(tr => {
    const c = [...tr.cells].map(x => x.innerText.trim());
    const d = (c[0].match(/(\d\d)\/(\d\d)\/(\d{4})/) || []);
    if (!d[0]) return null;
    return { d: d[3] + '-' + d[2] + '-' + d[1], adj: num(c[1]), c: num(c[2]), traded: c[6] !== '' && !/אין מסחר/.test(c[0]), reg: /רישום/.test(c[0]) };
  }).filter(Boolean);
  const total = +(((document.querySelector('.small-screen') || {}).textContent || '').match(/\/\s*(\d+)/) || [0, 1])[1];
  let all = [];
  for (let p = 1; p <= total; p++) {
    const rows = readPage(); all = all.concat(rows);
    if (p === total) break;
    const before = rows[0] && rows[0].d;
    document.querySelector('.ngx-pagination .pagination-next a').click();
    for (let i = 0; i < 40; i++) { await sleep(120); const r = readPage(); if (r[0] && r[0].d !== before) break; }
  }
  const seen = new Set(); all = all.filter(r => !seen.has(r.d) && seen.add(r.d)); all.sort((a, b) => a.d < b.d ? -1 : 1);
  const ye = [];
  for (let y = 2019; y <= 2026; y++) {
    const e = y + '-12-31', up = all.filter(r => r.d <= e), carry = up[up.length - 1], lt = up.filter(r => r.traded || r.reg).pop();
    if (lt) ye.push(y + '=' + lt.d + '|' + lt.c + '|' + lt.adj + (carry && carry.d !== lt.d ? '|carry:' + carry.d + '|' + carry.adj : ''));
  }
  const f0 = all[0];
  return { sec: location.pathname.split('/')[4], n: all.length, first: f0.d + (f0.reg ? '(reg)' : ''), ye: ye.join(' ') };
};
