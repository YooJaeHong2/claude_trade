"""Fetch the top-100 US companies by market cap and two years of daily closes.

Runs in GitHub Actions (or locally with internet access) and writes data/data.json.

    pip install yfinance pandas
    python scripts/fetch_data.py
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "data" / "data.json"
TOP_N = 100

# Large US-listed, US-headquartered companies. Ranked by live market cap at run
# time, so the list only needs to be a generous superset of the real top 100.
# One share class per company (GOOGL, BRK-B).
CANDIDATES = """
AAPL MSFT NVDA GOOGL AMZN META AVGO TSLA BRK-B LLY JPM WMT V ORCL MA XOM UNH NFLX
COST JNJ PG HD ABBV BAC KO PLTR CRM CVX AMD TMUS WFC CSCO ABT PM IBM MS GS MCD LIN
GE INTU AXP NOW DIS PEP TMO ISRG CAT VZ T UBER RTX BKNG QCOM TXN ADBE SPGI BA PGR
C AMGN SCHW BSX NEE AMAT LOW DHR PFE TJX BLK SYK UNP HON GILD ANET COP ETN MU KKR
DE VRTX PANW ADP LRCX CMCSA ADI KLAC MDT APH CRWD LMT BX ICE MO SBUX CB MMC CEG SO
WELL PLD DASH AMT HOOD COIN INTC APP MSTR NKE CME BMY ELV DUK CVS MCK WM CI SHW EQIX
MDLZ TT GD PH ORLY MMM ABNB CTAS AJG ZTS NOC HCA MCO PYPL ECL USB SNPS CDNS ITW RCL
PNC FI MAR TDG EMR AON WMB CMG APO REGN BK DELL MRVL CL HWM GEV VST SNOW NET FTNT
TRV AZO CSX ADSK COF NSC FDX KMI OKE SPG GM F SRE AEP DDOG RBLX CVNA AXON TEAM WDAY
JCI PSX MPC FCX NEM TGT EOG SLB HLT GLW WDC STX ALL MET AFL AIG
IBKR CRWV VRT PWR RSG ROP COR CHTR EA TTWO ROST CPRT PCAR AMP ALNY SOFI RDDT ZS
MSI CARR OXY LHX URI FAST GWW KR KDP KHC HSY GIS STZ CTVA DOW APD PSA O DLR CCI
VICI HUM IQV IDXX A BDX EW RMD DXCM GEHC CNC EXC D PCG XEL ED BKR TEL CIEN LITE
NXPI MCHP ON MPWR TER CMI ODFL PAYX AME VLO TRGP LNG ET EPD MPLX WBD ARES TOST
""".split()


def rnd(x: float) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), 2 if abs(x) >= 1 else 4)


def market_cap(sym: str) -> tuple[float | None, str, str]:
    """Return (market cap USD, name, sector)."""
    t = yf.Ticker(sym)
    cap, name, sector = None, sym, ""
    for attempt in range(3):
        try:
            info = t.info or {}
            cap = info.get("marketCap")
            name = info.get("shortName") or info.get("longName") or sym
            sector = info.get("sector") or ""
            if cap:
                return float(cap), name, sector
        except Exception as e:  # noqa: BLE001
            print(f"  info failed {sym} ({attempt + 1}): {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    try:
        cap = t.fast_info["marketCap"]
    except Exception as e:  # noqa: BLE001
        print(f"  fast_info failed {sym}: {e}", file=sys.stderr)
    return (float(cap) if cap else None), name, sector


def fill_latest_sessions(daily: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Yahoo's daily series omits the current session until well after the close
    (e.g. a run at 16:05 ET). Append any newer session from 60-minute bars: the
    last hourly bar's close is that day's closing price."""
    hourly = yf.download(tickers, period="5d", interval="60m", auto_adjust=True,
                         progress=False, threads=True)["Close"]
    if isinstance(hourly, pd.Series):
        hourly = hourly.to_frame(tickers[0])
    hourly = hourly.dropna(how="all")
    if hourly.empty:
        return daily
    idx = hourly.index
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York")
    by_day = hourly.groupby(idx.date).last()
    last_daily = daily.index[-1].date()
    for day, row in by_day.iterrows():
        if day > last_daily:
            print(f"  adding {day} from hourly bars (missing from daily series)")
            daily.loc[pd.Timestamp(day)] = row.reindex(daily.columns)
    return daily.sort_index()


def drawdown_episodes(hist: pd.Series, depth: float = -10.0) -> list:
    """Peak-to-recovery episodes deeper than `depth` %, over the full history.
    Each item: [peak date, peak, trough date, trough, recovery date or None]."""
    out, pk, tr, in_ep, peak = [], None, None, False, -math.inf
    for d, v in hist.items():
        if v >= peak:
            if in_ep:
                out.append((pk, tr, d))
            peak, pk, tr, in_ep = v, d, d, False
            continue
        if v < hist[tr]:
            tr = d
        if (v / peak - 1) * 100 <= depth:
            in_ep = True
    if in_ep:
        out.append((pk, tr, None))
    f = lambda d: d.strftime("%Y-%m-%d")
    return [[f(p), rnd(hist[p]), f(t), rnd(hist[t]), f(r) if r is not None else None]
            for p, t, r in out]


def main() -> None:
    print(f"Ranking {len(CANDIDATES)} candidates by market cap...")
    rows = []
    for sym in CANDIDATES:
        cap, name, sector = market_cap(sym)
        if cap:
            rows.append({"t": sym, "n": name, "s": sector, "mc": cap})
        time.sleep(0.2)
    if len(rows) < TOP_N:
        sys.exit(f"Only {len(rows)} market caps fetched; refusing to write partial data")
    rows.sort(key=lambda r: r["mc"], reverse=True)
    top = rows[:TOP_N]

    tickers = [r["t"] for r in top]
    print("Downloading full daily history...")
    full = yf.download(tickers, period="max", interval="1d", auto_adjust=True,
                       progress=False, threads=True)["Close"]
    if isinstance(full, pd.Series):
        full = full.to_frame(tickers[0])
    full = full.dropna(how="all").sort_index()
    full.index = pd.DatetimeIndex(full.index).tz_localize(None)
    full = fill_latest_sessions(full, tickers)

    start = full.index[-1] - pd.DateOffset(years=2)
    px = full.loc[full.index >= start]
    dates = [d.strftime("%Y-%m-%d") for d in px.index]

    stocks = []
    for rank, r in enumerate(top, 1):
        hist = full[r["t"]].dropna() if r["t"] in full else pd.Series(dtype=float)
        col = px[r["t"]] if r["t"] in px else pd.Series(index=px.index, dtype=float)
        closes = [rnd(v) for v in col.tolist()]
        if sum(c is not None for c in closes) < 20:
            print(f"  warning: little price data for {r['t']}", file=sys.stderr)
        before = hist.loc[hist.index < px.index[0]]
        ath_i = hist.idxmax() if len(hist) else None
        stocks.append({
            **r, "rank": rank, "c": closes,
            # highest close before the 2-year window: lets the page measure
            # drawdowns against the true all-time high, not just the window's
            "pk0": rnd(before.max()) if len(before) else None,
            "since": hist.index[0].strftime("%Y-%m-%d") if len(hist) else None,
            "ath": [rnd(hist.max()), ath_i.strftime("%Y-%m-%d")] if ath_i is not None else None,
            "ep": drawdown_episodes(hist),
        })

    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asOf": dates[-1],
        "dates": dates,
        "stocks": stocks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB), {len(dates)} days, as of {dates[-1]}")


if __name__ == "__main__":
    main()
