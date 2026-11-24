#!/usr/bin/env python3
"""
generate_data.py — Regenerate the dashboard's /data/*.json files from the
source Excel workbook "Feed Raw Material Price Dashboard..xlsx".

Usage:
    python3 generate_data.py [path/to/Feed Raw Material Price Dashboard..xlsx]

Reads the "Input File" sheet (rows 13–97 hold the 85 tracked materials) and
writes the seven JSON files the dashboard consumes:

    data/products.json          core price & sourcing dataset
    data/history.json           12-month interpolated trend per material
    data/countries.json         sourcing-country aggregation
    data/suppliers.json         Akij sourcing vs best-buy comparison
    data/signals.json           Go / Monitor / Risk signal cards
    data/recommendations.json   procurement action per material
    data/ai_insights.json       data-driven AI narrative

Everything the dashboard displays is read from these JSON files — no code
changes are required between data refreshes.
"""

import datetime as _dt
import json
import os
import sys

import openpyxl

# --------------------------------------------------------------------------
# Column layout of the "Input File" sheet (1-indexed)
# --------------------------------------------------------------------------
C = {
    "hs_code": 1, "product": 2, "unit": 3, "source": 4,
    "last_week": 5, "current_avg": 6, "last_month": 7, "six_mo": 8,
    "avg_2024": 9, "avg_2025": 10, "last_yr_ytd": 11, "ytd_2026": 12,
    "ytd_pct": 13, "wow_pct": 14, "mom_pct": 15, "yoy_pct": 16,
    "trend": 17, "next_wk": 18, "forecast_delta": 19,
    "country1": 20, "price1": 21, "country2": 22, "price2": 23,
    "country3": 24, "price3": 25, "best_buy": 26, "akij": 27,
    "risk": 28, "action": 29,
}

DATA_ROW_START = 13          # first product data row (1-indexed)
DATA_ROW_END = 97            # last product data row (inclusive)

AS_OF_CELL = "G4"            # as-of / last-updated date
MATERIALS_CELL = "O4"        # materials-tracked count

ANALYST = "Dr. Deepanjan Bhattacharya"

RISK_MAP = {
    "❓ REVIEW": "REVIEW",
    "✅ OPTIMAL": "OPTIMAL",
    "🔴 HIGH COST": "HIGH_COST",
    "🟠 MONITOR": "MONITOR",
    "⚠ ACCEPTABLE": "MONITOR",
    "-": "MONITOR",
}

TREND_MAP = {"↑": "up", "→": "flat", "↓": "down", "-": None}

MONTHS = [
    "Sep25", "Oct25", "Nov25", "Dec25", "Jan26",
    "Feb26", "Mar26", "Apr26", "May26", "Jun26", "Jul26", "Aug26",
]

HISTORY_NOTE = (
    "Monthly trend interpolated between tracked anchor points "
    "(2025 avg, 6-month avg, last-month avg, current avg, last-week price) "
    "for visualization purposes."
)

RECO_PRIORITY = {
    "Review Supplier": ("high", "danger"),
    "Diversify Source": ("high", "danger"),
    "Strong Buy": ("high", "success"),
    "Monitor": ("medium", "warning"),
    "Buy": ("medium", "success"),
    "Hold": ("low", "neutral"),
}

SIGNAL_META = {
    "OPTIMAL": ("GO", "success", "check-circle"),
    "MONITOR": ("MONITOR", "warning", "alert-circle"),
    "REVIEW": ("RISK", "danger", "alert-triangle"),
    "HIGH_COST": ("RISK", "danger", "alert-triangle"),
}


def num(value):
    """Coerce a cell to float, or None for missing / '-' values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def txt(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def hs_code(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    s = str(value).strip()
    if not s:
        return None
    return s.replace(", ", " / ")


def country_field(value):
    """Cheapest-origin / best-buy columns: empty or '-' -> None."""
    s = txt(value)
    if s in (None, "-"):
        return None
    return s


def akij_field(value):
    """Akij sourcing column: empty or '-' -> '-'. """
    s = txt(value)
    if s in (None, "-"):
        return "-"
    return s


def load_sheet(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    return wb["Input File"]


def read_products(ws):
    products = []
    for r in range(DATA_ROW_START, DATA_ROW_END + 1):
        g = lambda col: ws.cell(row=r, column=C[col]).value
        p = {
            "hsCode": hs_code(g("hs_code")),
            "product": txt(g("product")),
            "unit": txt(g("unit")),
            "lastWeekPrice": num(g("last_week")),
            "currentAvgPrice": num(g("current_avg")),
            "lastMonthAvg": num(g("last_month")),
            "sixMoAvg": num(g("six_mo")),
            "avg2024": num(g("avg_2024")),
            "avg2025": num(g("avg_2025")),
            "lastYearYtdAvg": num(g("last_yr_ytd")),
            "ytdAvg2026": num(g("ytd_2026")),
            "ytdPct": num(g("ytd_pct")),
            "wowPct": num(g("wow_pct")),
            "momPct": num(g("mom_pct")),
            "yoyPct": num(g("yoy_pct")),
            "trend": TREND_MAP.get(txt(g("trend"))),
            "nextWkForecast": num(g("next_wk")),
            "forecastDeltaPct": num(g("forecast_delta")),
            "cheapestCountry1": country_field(g("country1")),
            "price1": num(g("price1")),
            "cheapestCountry2": country_field(g("country2")),
            "price2": num(g("price2")),
            "cheapestCountry3": country_field(g("country3")),
            "price3": num(g("price3")),
            "bestBuyCountry": country_field(g("best_buy")),
            "akijSourcingCountry": akij_field(g("akij")),
            "riskSignal": RISK_MAP.get(txt(g("risk"))),
            "procurementAction": txt(g("action")),
        }
        if p["product"] is None:
            continue
        p["id"] = "MAT-{:03d}".format(len(products) + 1)
        p["source"] = txt(g("source"))
        products.append(p)
    return products


def as_of_date(ws):
    v = ws[AS_OF_CELL].value
    if isinstance(v, _dt.datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, _dt.date):
        return v.strftime("%Y-%m-%d")
    return str(v)


def build_products(ws):
    return {
        "asOfDate": as_of_date(ws),
        "materialsTracked": int(ws[MATERIALS_CELL].value or 0),
        "analyst": ANALYST,
        "products": read_products(ws),
    }


def interpolate_series(p):
    """12-month series from anchor points (see HISTORY_NOTE)."""
    anchors = [
        (0, p["avg2025"]),
        (4, p["sixMoAvg"]),
        (7, p["lastMonthAvg"]),
        (9, p["currentAvgPrice"]),
        (10, p["lastWeekPrice"]),
        (11, p["lastWeekPrice"]),
    ]
    anchors = [(i, v) for i, v in anchors if v is not None]
    if not anchors:
        return [None] * 12

    anchor_values = {i: v for i, v in anchors}
    first_i, first_v = anchors[0]
    last_i, last_v = anchors[-1]

    pts = [None] * 12
    for idx in range(12):
        if idx in anchor_values:
            pts[idx] = anchor_values[idx]   # raw anchor value (full precision)
        elif idx < first_i:
            pts[idx] = first_v              # forward-fill (raw)
        elif idx > last_i:
            pts[idx] = last_v               # backward-fill (raw)
        else:
            lo = hi = None
            for a, b in zip(anchors, anchors[1:]):
                if a[0] < idx < b[0]:
                    lo, hi = a, b
                    break
            if lo is None or hi is None:
                pts[idx] = first_v
            else:
                t = (idx - lo[0]) / (hi[0] - lo[0])
                pts[idx] = round(lo[1] + (hi[1] - lo[1]) * t, 2)

    return pts


def build_history(products):
    return {
        "months": MONTHS,
        "note": HISTORY_NOTE,
        "series": {p["id"]: interpolate_series(p) for p in products},
    }


def build_countries(products):
    appear = {}   # country -> list of (product, price)
    rank1 = {}    # country -> list of products where it is cheapest #1
    for p in products:
        slots = [
            (p["cheapestCountry1"], p["price1"]),
            (p["cheapestCountry2"], p["price2"]),
            (p["cheapestCountry3"], p["price3"]),
        ]
        for c, price in slots:
            if c:
                appear.setdefault(c, []).append((p["product"], price))
        if p["cheapestCountry1"]:
            rank1.setdefault(p["cheapestCountry1"], []).append(p["product"])

    countries = []
    for c, entries in appear.items():
        products_seen = []
        seen = set()
        for prod, _ in entries:
            if prod not in seen:
                seen.add(prod)
                products_seen.append(prod)
        prices = [price for _, price in entries if price is not None]
        avg = round(sum(prices) / len(prices), 1) if prices else None
        countries.append({
            "country": c,
            "productsSourced": len(products_seen),
            "rank1Count": len(rank1.get(c, [])),
            "totalAppearances": len(entries),
            "avgQuotedPrice": avg,
            "products": sorted(products_seen),
        })

    countries.sort(key=lambda x: (-x["rank1Count"], -x["totalAppearances"],
                                  -x["productsSourced"], x["country"]))
    return {"countries": countries}


def best_buy_price(p):
    return p["price1"]  # best-buy price is the #1 cheapest quoted price


def akij_quoted_price(p):
    for c, price in [(p["cheapestCountry1"], p["price1"]),
                     (p["cheapestCountry2"], p["price2"]),
                     (p["cheapestCountry3"], p["price3"])]:
        if c and c == p["akijSourcingCountry"] and price is not None:
            return price
    return None


def build_suppliers(products):
    suppliers = []
    for p in products:
        bbp = best_buy_price(p)
        akij = akij_quoted_price(p)
        gap = None
        if akij is not None and bbp:
            gap = round((akij - bbp) / bbp, 4)
        suppliers.append({
            "productId": p["id"],
            "product": p["product"],
            "akijSourcingCountry": p["akijSourcingCountry"],
            "akijQuotedPrice": akij,
            "bestBuyCountry": p["bestBuyCountry"],
            "bestBuyPrice": bbp,
            "costGapPct": gap,
            "riskSignal": p["riskSignal"],
            "procurementAction": p["procurementAction"],
        })
    return {"suppliers": suppliers}


def signal_description(p):
    akij = p["akijSourcingCountry"]
    if p["riskSignal"] == "OPTIMAL":
        return f"{p['product']} sourcing from {akij} is aligned with the best available market price."
    if p["riskSignal"] == "HIGH_COST":
        return f"{p['product']} sourced from {akij} costs meaningfully more than the best available origin ({p['bestBuyCountry']})."
    if p["riskSignal"] == "MONITOR":
        return f"{p['product']} has no confirmed Akij sourcing country on file yet; price trend should be monitored before committing to an origin."
    return f"{p['product']} sourced from {akij} needs supplier review amid unclear pricing signals."


def build_signals(products):
    signals = []
    for p in products:
        label, color, icon = SIGNAL_META[p["riskSignal"]]
        signals.append({
            "productId": p["id"],
            "product": p["product"],
            "signal": p["riskSignal"],
            "label": label,
            "color": color,
            "icon": icon,
            "description": signal_description(p),
        })
    return {"signals": signals}


def build_recommendations(products):
    recs = []
    for p in products:
        priority, color = RECO_PRIORITY.get(p["procurementAction"], ("low", "neutral"))
        recs.append({
            "productId": p["id"],
            "product": p["product"],
            "action": p["procurementAction"],
            "priority": priority,
            "color": color,
            "riskSignal": p["riskSignal"],
            "wowPct": p["wowPct"],
            "forecastDeltaPct": p["forecastDeltaPct"],
        })
    return {"recommendations": recs}


def build_insights(products, ws):
    n = len(products)
    wow = [p["wowPct"] for p in products if p["wowPct"] is not None]
    avg_wow = sum(wow) / len(wow) if wow else 0.0

    priced = [p for p in products if p["currentAvgPrice"] is not None]
    cheapest = min(priced, key=lambda p: p["currentAvgPrice"])
    most_expensive = max(priced, key=lambda p: p["currentAvgPrice"])

    riser = max(products, key=lambda p: p["wowPct"] if p["wowPct"] is not None else -1e9)
    dropper = min(products, key=lambda p: p["wowPct"] if p["wowPct"] is not None else 1e9)

    moved = sum(1 for p in products if p["wowPct"] is not None and abs(p["wowPct"]) >= 0.10)
    priced_n = sum(1 for p in products if p["wowPct"] is not None)

    review = sum(1 for p in products if p["riskSignal"] == "REVIEW")
    high_cost = sum(1 for p in products if p["riskSignal"] == "HIGH_COST")
    no_origin = sum(1 for p in products if p["akijSourcingCountry"] in (None, "-"))

    high_cost_names = ", ".join(
        p["product"] for p in products if p["riskSignal"] == "HIGH_COST"
    )

    def pct(v):
        return f"{v * 100:+.1f}%"

    insights = [
        {
            "title": f"Portfolio tracks {n} raw materials",
            "text": (
                f"The tracked universe spans {n} raw materials this cycle — "
                f"averaging {pct(avg_wow)} week-on-week."
            ),
        },
        {
            "title": f"{riser['product']} spikes as {dropper['product']} slides",
            "text": (
                f"{riser['product']} posted the sharpest weekly gain at "
                f"{pct(riser['wowPct'])}, while {dropper['product']} fell "
                f"{pct(dropper['wowPct'])} WoW; {moved} of {priced_n} priced "
                f"materials moved more than ±10% week-on-week."
            ),
        },
        {
            "title": f"{cheapest['product']} cheapest, {most_expensive['product']} most expensive",
            "text": (
                f"{cheapest['product']} remains the lowest-priced tracked material "
                f"at roughly ${cheapest['currentAvgPrice']:,.0f}/MT, while "
                f"{most_expensive['product']} is the most expensive at about "
                f"${most_expensive['currentAvgPrice']:,.0f}/MT."
            ),
        },
        {
            "title": f"{review} materials flagged for supplier review, {high_cost} confirmed high-cost",
            "text": (
                f"{high_cost_names} carry confirmed High Cost signals versus "
                f"alternative sourcing, while {review} additional materials are "
                f"flagged for supplier review."
            ),
        },
        {
            "title": f"{no_origin} materials still lack a confirmed origin",
            "text": (
                f"{no_origin} of the tracked materials have no confirmed Akij "
                f"sourcing country on file yet — largely the newly added feed "
                f"premix, supplement, and specialty meal lines."
            ),
        },
    ]
    return {"insights": insights}


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    default = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Feed Raw Material Price Dashboard..xlsx",
    )
    src = sys.argv[1] if len(sys.argv) > 1 else default
    if not os.path.exists(src):
        sys.exit(f"Workbook not found: {src}")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out_dir, exist_ok=True)

    ws = load_sheet(src)
    products = build_products(ws)["products"]

    write_json(os.path.join(out_dir, "products.json"), {
        "asOfDate": as_of_date(ws),
        "materialsTracked": int(ws[MATERIALS_CELL].value or 0),
        "analyst": ANALYST,
        "products": products,
    })
    write_json(os.path.join(out_dir, "history.json"), build_history(products))
    write_json(os.path.join(out_dir, "countries.json"), build_countries(products))
    write_json(os.path.join(out_dir, "suppliers.json"), build_suppliers(products))
    write_json(os.path.join(out_dir, "signals.json"), build_signals(products))
    write_json(os.path.join(out_dir, "recommendations.json"), build_recommendations(products))
    write_json(os.path.join(out_dir, "ai_insights.json"), build_insights(products, ws))

    print(f"Wrote {len(products)} materials to {out_dir}")


if __name__ == "__main__":
    main()
