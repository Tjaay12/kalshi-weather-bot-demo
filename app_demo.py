import csv
import re
from collections import defaultdict

import streamlit as st


SIMULATED_TRADES_CSV = "simulated_trades.csv"
GRADED_SIMULATED_TRADES_CSV = "graded_simulated_trades.csv"

DEGREE_SYMBOL = "\N{DEGREE SIGN}"
DEGREE_MARKERS = ("Ã‚Â°", "Â°", DEGREE_SYMBOL)
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
    normalized = normalize_title(title)
    return normalized.replace("**", "").strip()


def format_temp_value(value):
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
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


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value):
    return str(value).strip().lower() == "true"


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

    simulated_lookup = {}
    for row in simulated_rows:
        simulated_lookup[trade_key(row)] = row

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
            "result_display": "✅ WIN" if trade_won else "❌ LOSS",
            "audit_summary": (
                f"{row.get('city_name', '')} | {condition} | {row.get('side', '')} | "
                f"actual: {format_temp_value(actual_high_temp)} | "
                f"outcome: {row.get('resolved_outcome', '')} | "
                f"{'✅ WIN' if trade_won else '❌ LOSS'}"
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

    return {
        "total_trades": total_trades,
        "wins": wins,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "total_dollars_bet": total_dollars_bet,
        "roi": roi,
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


def render_intro():
    st.title("Weather Market Audit Demo")
    st.caption("Built with Codex for the Codex Creator Challenge")

    st.markdown(
        """
        <div style="padding:0.9rem 1rem;border:1px solid #f0c36d;background:#fff8e6;border-radius:0.75rem;">
            <strong>PUBLIC DEMO MODE</strong> — read-only dashboard. Live trading, API keys, and private execution controls removed.
        </div>
        """,
        unsafe_allow_html=True,
    )

    problem_col, solution_col = st.columns(2)
    with problem_col:
        st.subheader("Problem")
        st.write("Weather markets can misprice discrete temperature outcomes, creating confusing odds for traders trying to reason about fair value.")
    with solution_col:
        st.subheader("Solution")
        st.write("This AI-assisted decision system compares market prices against model-estimated fair value, simulates decisions, and audits the results after official weather resolution.")


def render_how_it_works():
    st.subheader("How It Works")
    st.caption("Why it matters: judges and users should be able to understand the workflow in one quick scan.")

    cols = st.columns(5)
    steps = [
        ("1. Data ingestion", "Saved market snapshots and resolved outcomes are loaded from local CSVs for a safe, reproducible demo."),
        ("2. Probability model", "A weather-specific model estimates fair probabilities for each contract based on forecasted temperature ranges."),
        ("3. Edge detection", "Market prices are compared to model-estimated fair value to identify where pricing looked attractive."),
        ("4. Simulated execution", "Qualified trades are paper-traded only, keeping the system useful without taking live market risk."),
        ("5. NWS grading", "Resolved trades are graded against National Weather Service actual highs to measure real-world performance."),
    ]

    for col, (title, body) in zip(cols, steps):
        with col:
            st.markdown(f"**{title}**")
            st.write(body)


def render_results(simulated_rows, graded_rows):
    st.subheader("Results")
    st.caption("Why it matters: this section compresses the headline value of the project into a few decision-ready metrics.")

    summary = summarize_results(graded_rows)
    metrics = st.columns(5)
    metrics[0].metric("Total simulated trades", len(simulated_rows))
    metrics[1].metric("Graded trades", summary["total_trades"])
    metrics[2].metric("Win rate", f"{summary['win_rate']:.2f}%")
    metrics[3].metric("Total PnL", f"${summary['total_pnl']:.2f}")
    metrics[4].metric("ROI", f"{summary['roi'] * 100:.2f}%")

    st.dataframe(
        summarize_city_performance(graded_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "win_rate": st.column_config.NumberColumn(format="%.2f%%"),
            "total_pnl": st.column_config.NumberColumn(format="$%.2f"),
            "roi": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )


def render_insights(graded_rows):
    st.subheader("Insights")
    st.caption("Why it matters: breakdowns by side and edge bucket show where the system appears stronger and where it deserves caution.")

    insight_tabs = st.tabs(["YES vs NO", "Edge Buckets"])

    with insight_tabs[0]:
        st.dataframe(
            summarize_side_performance(graded_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn(format="%.2f%%"),
                "total_pnl": st.column_config.NumberColumn(format="$%.2f"),
                "avg_pnl_per_trade": st.column_config.NumberColumn(format="$%.2f"),
                "total_dollars_bet": st.column_config.NumberColumn(format="$%.2f"),
                "roi": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

    with insight_tabs[1]:
        st.dataframe(
            summarize_edge_buckets(graded_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn(format="%.2f%%"),
                "total_pnl": st.column_config.NumberColumn(format="$%.2f"),
                "avg_pnl": st.column_config.NumberColumn(format="$%.2f"),
                "avg_dollars_bet": st.column_config.NumberColumn(format="$%.2f"),
                "roi": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )


def render_audit_view(graded_rows):
    st.subheader("Audit View")
    st.caption("Why it matters: every graded trade can be inspected against the actual temperature, settlement condition, and final win/loss outcome.")

    audit_rows = build_audit_rows(graded_rows)
    city_options = ["All cities"] + sorted({row["city_name"] for row in audit_rows})
    side_options = ["All sides", "YES", "NO"]
    result_options = ["All results", "✅ WIN", "❌ LOSS"]

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

    st.dataframe(
        filtered_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "actual_high_temp": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def main():
    st.set_page_config(page_title="Weather Market Audit Demo", layout="wide")

    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    simulated_rows, graded_rows = load_demo_data()

    render_intro()
    render_how_it_works()
    render_results(simulated_rows, graded_rows)
    render_insights(graded_rows)
    render_audit_view(graded_rows)


if __name__ == "__main__":
    main()
