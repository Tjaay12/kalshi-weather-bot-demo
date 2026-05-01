import csv
import re
from collections import defaultdict

import streamlit as st


SIMULATED_TRADES_CSV = "simulated_trades.csv"
GRADED_SIMULATED_TRADES_CSV = "graded_simulated_trades.csv"

DEGREE_SYMBOL = "\N{DEGREE SIGN}"
DEGREE_MARKERS = ("\u00c2\u00b0", "\u00b0", DEGREE_SYMBOL)
DEGREE_REGEX = re.escape(DEGREE_SYMBOL)


def load_csv_rows(filename):
    with open(filename, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def trade_key(trade):
    return (
        trade.get("timestamp", ""),
        trade.get("event_ticker", ""),
        trade.get("market_ticker", ""),
        trade.get("side", ""),
    )


def normalize_title(title):
    normalized = str(title or "")
    for marker in DEGREE_MARKERS:
        normalized = normalized.replace(marker, DEGREE_SYMBOL)
    return normalized


def clean_title(title):
    return normalize_title(title).replace("**", "").strip()


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value):
    return str(value).strip().lower() == "true"


def format_temp_value(value):
    numeric_value = to_float(value, None)
    if numeric_value is None:
        return str(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return f"{numeric_value:.2f}".rstrip("0").rstrip(".")


def readable_condition_from_title(title):
    normalized_title = clean_title(title).lower()
    patterns = [
        (
            rf"(-?\d+(?:\.\d+)?)\s*{DEGREE_REGEX}\s*or\s*below",
            lambda match: f"{format_temp_value(match.group(1))}{DEGREE_SYMBOL} or below",
        ),
        (
            rf"be\s*<\s*(-?\d+(?:\.\d+)?)\s*(?:{DEGREE_REGEX})?",
            lambda match: f"<{format_temp_value(match.group(1))}{DEGREE_SYMBOL}",
        ),
        (
            rf"(-?\d+(?:\.\d+)?)\s*{DEGREE_REGEX}\s*or\s*above",
            lambda match: f"{format_temp_value(match.group(1))}{DEGREE_SYMBOL} or above",
        ),
        (
            rf"be\s*>\s*(-?\d+(?:\.\d+)?)\s*(?:{DEGREE_REGEX})?",
            lambda match: f">{format_temp_value(match.group(1))}{DEGREE_SYMBOL}",
        ),
        (
            rf"be\s*(-?\d+(?:\.\d+)?)\s*(?:{DEGREE_REGEX})?\s*-\s*(-?\d+(?:\.\d+)?)\s*(?:{DEGREE_REGEX})?",
            lambda match: (
                f"{format_temp_value(match.group(1))}{DEGREE_SYMBOL} "
                f"to {format_temp_value(match.group(2))}{DEGREE_SYMBOL}"
            ),
        ),
        (
            rf"be\s*(-?\d+(?:\.\d+)?)\s*(?:{DEGREE_REGEX})?\s*to\s*(-?\d+(?:\.\d+)?)\s*(?:{DEGREE_REGEX})?",
            lambda match: (
                f"{format_temp_value(match.group(1))}{DEGREE_SYMBOL} "
                f"to {format_temp_value(match.group(2))}{DEGREE_SYMBOL}"
            ),
        ),
        (
            rf"(-?\d+(?:\.\d+)?)\s*(?:{DEGREE_REGEX})?\s*-\s*(-?\d+(?:\.\d+)?)\s*{DEGREE_REGEX}",
            lambda match: (
                f"{format_temp_value(match.group(1))}{DEGREE_SYMBOL} "
                f"to {format_temp_value(match.group(2))}{DEGREE_SYMBOL}"
            ),
        ),
        (
            rf"(-?\d+(?:\.\d+)?)\s*{DEGREE_REGEX}\s*to\s*(-?\d+(?:\.\d+)?)\s*{DEGREE_REGEX}",
            lambda match: (
                f"{format_temp_value(match.group(1))}{DEGREE_SYMBOL} "
                f"to {format_temp_value(match.group(2))}{DEGREE_SYMBOL}"
            ),
        ),
    ]

    for pattern, formatter in patterns:
        match = re.search(pattern, normalized_title)
        if match:
            return formatter(match)

    return ""


def get_edge_bucket(best_edge):
    if 0.02 <= best_edge < 0.05:
        return "0.02 <= edge < 0.05"
    if 0.05 <= best_edge < 0.10:
        return "0.05 <= edge < 0.10"
    if best_edge >= 0.10:
        return "edge >= 0.10"
    return "edge < 0.02"


@st.cache_data
def load_demo_data():
    simulated_rows = load_csv_rows(SIMULATED_TRADES_CSV)
    graded_rows = load_csv_rows(GRADED_SIMULATED_TRADES_CSV)

    simulated_lookup = {trade_key(row): row for row in simulated_rows}
    enriched_graded_rows = []

    for row in graded_rows:
        simulated_row = simulated_lookup.get(trade_key(row), {})
        title = clean_title(simulated_row.get("title", ""))
        condition = readable_condition_from_title(title)
        trade_won = to_bool(row.get("trade_won", ""))
        actual_high_temp = to_float(row.get("actual_high_temp", 0), 0.0)
        recommended_position = to_float(row.get("recommended_position_dollars", 0), 0.0)
        realized_pnl = to_float(row.get("realized_pnl", 0), 0.0)
        best_edge = to_float(row.get("best_edge", 0), 0.0)

        enriched_graded_rows.append({
            **row,
            "title": title,
            "condition": condition,
            "trade_won_bool": trade_won,
            "actual_high_temp_float": actual_high_temp,
            "recommended_position_float": recommended_position,
            "realized_pnl_float": realized_pnl,
            "best_edge_float": best_edge,
            "result_display": "WIN" if trade_won else "LOSS",
            "audit_summary": (
                f"{row.get('city_name', '')} | {condition} | {row.get('side', '')} | "
                f"actual: {format_temp_value(actual_high_temp)} | "
                f"outcome: {row.get('resolved_outcome', '')} | "
                f"{'WIN' if trade_won else 'LOSS'}"
            ),
        })

    return simulated_rows, enriched_graded_rows


def summarize_results(graded_rows):
    total_trades = len(graded_rows)
    wins = sum(1 for row in graded_rows if row["trade_won_bool"])
    total_pnl = sum(row["realized_pnl_float"] for row in graded_rows)
    total_dollars_bet = sum(row["recommended_position_float"] for row in graded_rows)
    roi = (total_pnl / total_dollars_bet) if total_dollars_bet else 0.0
    win_rate = (wins / total_trades * 100.0) if total_trades else 0.0
    avg_edge = (
        sum(row["best_edge_float"] for row in graded_rows) / total_trades
        if total_trades else 0.0
    )

    return {
        "total_trades": total_trades,
        "wins": wins,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "total_dollars_bet": total_dollars_bet,
        "roi": roi,
        "avg_edge": avg_edge,
    }


def summarize_side_performance(graded_rows):
    grouped = defaultdict(list)
    for row in graded_rows:
        grouped[row.get("side", "").strip().upper()].append(row)

    rows = []
    for side in ("YES", "NO"):
        side_rows = grouped.get(side, [])
        trades = len(side_rows)
        wins = sum(1 for row in side_rows if row["trade_won_bool"])
        total_pnl = sum(row["realized_pnl_float"] for row in side_rows)
        total_bet = sum(row["recommended_position_float"] for row in side_rows)
        rows.append({
            "side": side,
            "total_trades": trades,
            "win_rate": (wins / trades * 100.0) if trades else 0.0,
            "total_pnl": total_pnl,
            "avg_pnl_per_trade": (total_pnl / trades) if trades else 0.0,
            "total_dollars_bet": total_bet,
            "roi": (total_pnl / total_bet) if total_bet else 0.0,
        })

    return rows


def summarize_edge_buckets(graded_rows):
    grouped = defaultdict(list)
    for row in graded_rows:
        grouped[get_edge_bucket(row["best_edge_float"])].append(row)

    ordered_buckets = [
        "0.02 <= edge < 0.05",
        "0.05 <= edge < 0.10",
        "edge >= 0.10",
    ]

    rows = []
    for bucket in ordered_buckets:
        bucket_rows = grouped.get(bucket, [])
        trades = len(bucket_rows)
        wins = sum(1 for row in bucket_rows if row["trade_won_bool"])
        total_pnl = sum(row["realized_pnl_float"] for row in bucket_rows)
        total_bet = sum(row["recommended_position_float"] for row in bucket_rows)
        rows.append({
            "edge_bucket": bucket,
            "trades": trades,
            "win_rate": (wins / trades * 100.0) if trades else 0.0,
            "total_pnl": total_pnl,
            "avg_pnl": (total_pnl / trades) if trades else 0.0,
            "avg_dollars_bet": (total_bet / trades) if trades else 0.0,
            "roi": (total_pnl / total_bet) if total_bet else 0.0,
        })

    return rows


def summarize_city_performance(graded_rows):
    grouped = defaultdict(list)
    for row in graded_rows:
        grouped[row.get("city_name", "Unknown")].append(row)

    rows = []
    for city_name in sorted(grouped):
        city_rows = grouped[city_name]
        trades = len(city_rows)
        wins = sum(1 for row in city_rows if row["trade_won_bool"])
        total_pnl = sum(row["realized_pnl_float"] for row in city_rows)
        total_bet = sum(row["recommended_position_float"] for row in city_rows)
        rows.append({
            "city_name": city_name,
            "trades": trades,
            "win_rate": (wins / trades * 100.0) if trades else 0.0,
            "total_pnl": total_pnl,
            "roi": (total_pnl / total_bet) if total_bet else 0.0,
        })

    return rows


def build_audit_rows(graded_rows):
    rows = []
    for row in graded_rows:
        rows.append({
            "city_name": row.get("city_name", ""),
            "market_ticker": row.get("market_ticker", ""),
            "condition": row.get("condition", ""),
            "side": row.get("side", ""),
            "actual_high_temp": row["actual_high_temp_float"],
            "resolved_outcome": row.get("resolved_outcome", ""),
            "trade_won": row["trade_won_bool"],
            "result_display": row["result_display"],
            "audit_summary": row["audit_summary"],
        })

    rows.sort(key=lambda item: (item["city_name"], item["market_ticker"]))
    return rows


def render_section_header(title, body=None):
    st.markdown(f"## {title}")
    if body:
        st.write(body)


def render_hero():
    st.title("Weather Market Audit Demo")
    st.markdown(
        "### This project identifies and exploits inefficiencies in weather prediction markets using data-driven expected value analysis."
    )
    st.caption("Built with Codex")

    st.markdown(
        """
        <div style="padding: 0.95rem 1.1rem; border-radius: 0.8rem; border: 1px solid #e5e7eb; background: #f8fafc; font-weight: 600;">
            PUBLIC DEMO MODE - No live trading, no API keys, read-only simulation
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_problem_solution():
    cols = st.columns(2)
    with cols[0]:
        render_section_header(
            "Problem",
            (
                "Prediction markets turn uncertain forecasts into tradable prices, but those prices do not always line up with "
                "real-world weather expectations. When the market price drifts away from a reasonable probability estimate, "
                "a disciplined trader can end up with a measurable edge."
            ),
        )
    with cols[1]:
        render_section_header(
            "Solution",
            (
                "This bot compares model-estimated probability against market price, looks for positive expected value, and only "
                "simulates trades when the edge clears a defined threshold. The public demo strips out live execution and shows "
                "the full decision-and-grading loop in a safe read-only format."
            ),
        )


def render_how_it_works():
    render_section_header("How It Works")
    st.markdown(
        """
        - **Pull market data** from saved local snapshots of simulated trades and graded results.
        - **Estimate true probability** for each weather contract using a forecast-informed model.
        - **Calculate edge** by comparing market price with model-estimated fair value.
        - **Simulate trade** decisions instead of sending live orders.
        - **Grade using actual outcomes** from official weather observations after the event resolves.
        """
    )


def render_results(simulated_rows, graded_rows):
    render_section_header(
        "Results",
        "Win rate shows how often the simulated side matched the resolved market outcome. PnL and ROI show whether the paper trading decisions would have made money after sizing and grading."
    )

    summary = summarize_results(graded_rows)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Total simulated trades", len(simulated_rows))
    metric_cols[1].metric("Graded trades", summary["total_trades"])
    metric_cols[2].metric("Win rate", f"{summary['win_rate']:.2f}%")
    metric_cols[3].metric("Total PnL", f"${summary['total_pnl']:.2f}")
    metric_cols[4].metric("ROI", f"{summary['roi'] * 100:.2f}%")

    submetric_cols = st.columns(3)
    submetric_cols[0].metric("Wins", summary["wins"])
    submetric_cols[1].metric("Total dollars bet", f"${summary['total_dollars_bet']:.2f}")
    submetric_cols[2].metric("Average edge", f"{summary['avg_edge']:.3f}")

    st.caption("City-level performance helps show where the workflow appears strongest across the demo dataset.")
    st.dataframe(
        summarize_city_performance(graded_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "city_name": st.column_config.TextColumn("City"),
            "trades": st.column_config.NumberColumn("Trades"),
            "win_rate": st.column_config.NumberColumn("Win rate", format="%.2f%%"),
            "total_pnl": st.column_config.NumberColumn("Total PnL", format="$%.2f"),
            "roi": st.column_config.NumberColumn("ROI", format="%.2f%%"),
        },
    )


def render_key_insight():
    render_section_header("Key Insight")
    st.write(
        "The strategy shows positive ROI by targeting high-edge opportunities. In the current simulated dataset, "
        "NO-side trades account for most of the profit, suggesting that some weather buckets may be overpriced "
        "relative to forecast-based probabilities."
    )


def render_insights(graded_rows):
    render_section_header(
        "Insights",
        "These breakdowns make it easier to judge whether performance changes by trade side or by the size of the detected edge."
    )

    tabs = st.tabs(["YES vs NO performance", "Edge bucket performance"])

    with tabs[0]:
        st.caption("This table compares how the system performed when taking the YES side versus the NO side.")
        st.dataframe(
            summarize_side_performance(graded_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "side": st.column_config.TextColumn("Side"),
                "total_trades": st.column_config.NumberColumn("Trades"),
                "win_rate": st.column_config.NumberColumn("Win rate", format="%.2f%%"),
                "total_pnl": st.column_config.NumberColumn("Total PnL", format="$%.2f"),
                "avg_pnl_per_trade": st.column_config.NumberColumn("Avg PnL / trade", format="$%.2f"),
                "total_dollars_bet": st.column_config.NumberColumn("Total dollars bet", format="$%.2f"),
                "roi": st.column_config.NumberColumn("ROI", format="%.2f%%"),
            },
        )

    with tabs[1]:
        st.caption("Edge buckets help show whether stronger expected-value signals translated into better graded outcomes.")
        st.dataframe(
            summarize_edge_buckets(graded_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "edge_bucket": st.column_config.TextColumn("Edge bucket"),
                "trades": st.column_config.NumberColumn("Trades"),
                "win_rate": st.column_config.NumberColumn("Win rate", format="%.2f%%"),
                "total_pnl": st.column_config.NumberColumn("Total PnL", format="$%.2f"),
                "avg_pnl": st.column_config.NumberColumn("Avg PnL", format="$%.2f"),
                "avg_dollars_bet": st.column_config.NumberColumn("Avg dollars bet", format="$%.2f"),
                "roi": st.column_config.NumberColumn("ROI", format="%.2f%%"),
            },
        )


def render_audit_view(graded_rows):
    render_section_header(
        "Audit View",
        "This is the most transparent part of the demo: each row shows the market condition, chosen side, actual high temperature, resolved outcome, and whether the simulated trade won or lost."
    )

    audit_rows = build_audit_rows(graded_rows)
    city_options = ["All cities"] + sorted({row["city_name"] for row in audit_rows})
    side_options = ["All sides", "YES", "NO"]
    result_options = ["All results", "WIN", "LOSS"]

    filter_cols = st.columns(3)
    selected_city = filter_cols[0].selectbox("City filter", city_options)
    selected_side = filter_cols[1].selectbox("Side filter", side_options)
    selected_result = filter_cols[2].selectbox("Result filter", result_options)

    filtered_rows = []
    for row in audit_rows:
        if selected_city != "All cities" and row["city_name"] != selected_city:
            continue
        if selected_side != "All sides" and row["side"] != selected_side:
            continue
        if selected_result != "All results" and row["result_display"] != selected_result:
            continue
        filtered_rows.append(row)

    st.caption(
        f"Column guide: `condition` is the readable market rule (for example `<61{DEGREE_SYMBOL}` or `70{DEGREE_SYMBOL} to 71{DEGREE_SYMBOL}`), "
        "`resolved_outcome` is the winning market side, and `trade_won` indicates whether the simulated position matched that outcome."
    )
    st.dataframe(
        filtered_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "city_name": st.column_config.TextColumn("City"),
            "market_ticker": st.column_config.TextColumn("Market ticker"),
            "condition": st.column_config.TextColumn("Condition"),
            "side": st.column_config.TextColumn("Side taken"),
            "actual_high_temp": st.column_config.NumberColumn("Actual high temp", format="%.2f"),
            "resolved_outcome": st.column_config.TextColumn("Resolved outcome"),
            "trade_won": st.column_config.CheckboxColumn("Trade won"),
            "result_display": st.column_config.TextColumn("Result"),
            "audit_summary": st.column_config.TextColumn("Audit summary"),
        },
    )


def render_limitations():
    render_section_header("Limitations")
    st.write(
        "This demo uses historical simulated trades and a simplified probability model. It does not model all "
        "real-world execution constraints, including slippage, order book depth, liquidity limits, or failed "
        "fills. Results are not financial advice."
    )


def render_future_improvements():
    render_section_header("Future Improvements")
    st.markdown(
        """
        - Add liquidity-aware position sizing
        - Add live order book depth analysis
        - Improve probability calibration with more historical weather data
        - Expand to more cities and other prediction market categories
        - Add automated daily grading and reporting
        """
    )


def main():
    st.set_page_config(page_title="Weather Market Audit Demo", layout="wide")

    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    simulated_rows, graded_rows = load_demo_data()

    render_hero()
    st.write("")
    render_problem_solution()
    st.write("")
    render_how_it_works()
    st.write("")
    render_results(simulated_rows, graded_rows)
    st.write("")
    render_key_insight()
    st.write("")
    render_insights(graded_rows)
    st.write("")
    render_audit_view(graded_rows)
    st.write("")
    render_limitations()
    st.write("")
    render_future_improvements()


if __name__ == "__main__":
    main()
