import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

BASE = Path(__file__).parent
DATA = BASE / "data"

st.set_page_config(
    page_title="Vireo Audio — Support Coach",
    page_icon="🎧",
    layout="wide"
)

SLA_MIN = {
    "chat": 15,
    "voice": 120,
    "social": 240,
    "email": 480
}

CHANNEL_COST = {
    "chat": 210,
    "email": 260,
    "voice": 520,
    "social": 240
}

SLA_CREDIT = 350
AGENT_HOUR_COST = 165


@st.cache_data
def load_data(tickets_file=None, agents_file=None):
    t = pd.read_csv(tickets_file or DATA / "tickets.csv")
    a = pd.read_csv(agents_file or DATA / "agents.csv")

    t["created"] = pd.to_datetime(
        t["created_at"],
        errors="coerce"
    )

    t["first_response"] = pd.to_datetime(
        t["first_response_at"],
        errors="coerce"
    )

    t["resolved"] = pd.to_datetime(
        t["resolved_at"],
        errors="coerce"
    )

    # Policy/README:
    # Migrated legacy resolution timestamps were reconstructed from UTC.
    # Standard helpdesk timestamps are displayed in IST.
    # Convert legacy resolution only.
    legacy = (
        t["source_system"].eq("legacy_fd")
        & t["resolved"].notna()
    )

    t.loc[legacy, "resolved"] = (
        t.loc[legacy, "resolved"]
        + pd.Timedelta(hours=5, minutes=30)
    )

    t["handle_min"] = (
        t["resolved"] - t["first_response"]
    ).dt.total_seconds() / 60

    t["sla_target_min"] = t["channel"].map(SLA_MIN)

    first_response_min = (
        t["first_response"] - t["created"]
    ).dt.total_seconds() / 60

    t["sla_breach"] = (
        first_response_min > t["sla_target_min"]
    )

    t["month"] = (
        t["created"]
        .dt.to_period("M")
        .astype(str)
    )

    t = t.merge(
        a[["agent_id", "name", "team", "tier"]],
        on="agent_id",
        how="left"
    )

    return t, a


def pct_rank(s, ascending=True):
    return s.rank(
        pct=True,
        ascending=ascending,
        method="average"
    )


def build_metrics(t, start, end):
    x = t[
        (t["created"] >= pd.Timestamp(start))
        & (t["created"] < pd.Timestamp(end))
    ].copy()

    # Vireo policy defines Tier 1 as Chat, Email,
    # and Voice Frontline.
    # Logistics, Billing, and Returns Desk are
    # operational teams but not Tier 1.
    tier1_teams = {
        "Chat Frontline",
        "Email Frontline",
        "Voice Frontline"
    }

    x = x[
        x["team"].isin(tier1_teams)
    ].copy()

    g = (
        x.groupby(
            ["agent_id", "name", "team"],
            dropna=False
        )
        .agg(
            tickets=("ticket_id", "size"),
            csat_responses=("csat_score", "count"),
            csat=("csat_score", "mean"),
            median_handle_min=("handle_min", "median"),
            sla_breaches=("sla_breach", "sum"),
            sla_rate=("sla_breach", "mean"),
            transfers=("transfers", "sum"),
        )
        .reset_index()
    )

    # Peer-normalize inside team to avoid
    # comparing structurally different queues directly.
    for team, idx in g.groupby("team").groups.items():
        ids = list(idx)

        g.loc[ids, "bad_csat_rank"] = pct_rank(
            g.loc[ids, "csat"],
            ascending=True
        )

        g.loc[ids, "bad_handle_rank"] = pct_rank(
            g.loc[ids, "median_handle_min"],
            ascending=True
        )

        g.loc[ids, "bad_sla_rank"] = pct_rank(
            g.loc[ids, "sla_rate"],
            ascending=True
        )

    eligible = g[
        (g["csat_responses"] >= 30)
        & (g["tickets"] >= 30)
    ].copy()

    eligible["risk_score"] = (
        0.50 * eligible["bad_csat_rank"]
        + 0.30 * eligible["bad_handle_rank"]
        + 0.20 * eligible["bad_sla_rank"]
    )

    eligible = eligible.sort_values(
        "risk_score",
        ascending=False
    )

    return x, g, eligible


def format_minutes(m):
    if pd.isna(m):
        return "—"

    m = float(m)

    if m < 60:
        return f"{m:.0f} min"

    h = m / 60

    if h < 24:
        return f"{h:.1f} h"

    return f"{h / 24:.1f} d"


def extract_themes(ticket_subset):
    """
    Map ticket text to human-readable operational themes
    instead of raw word counts.
    """

    text_parts = []

    for col in [
        "customer_message",
        "agent_notes"
    ]:
        if col in ticket_subset.columns:
            text_parts.extend(
                ticket_subset[col]
                .dropna()
                .astype(str)
                .str.lower()
                .tolist()
            )

    # FIX:
    # Convert the list of text values into one string.
    text = " ".join(text_parts)

    theme_rules = {
        "Invoice / billing": [
            "invoice",
            "gst",
            "tax",
            "payment",
            "charged",
            "bill"
        ],

        "Delivery / shipping": [
            "delivery",
            "delayed",
            "delay",
            "courier",
            "shipment",
            "tracking",
            "transit",
            "dispatch"
        ],

        "Warranty / RMA": [
            "rma",
            "warranty",
            "service centre",
            "service center",
            "repair",
            "replacement",
            "fault"
        ],

        "Account / order updates": [
            "account",
            "update",
            "updated",
            "address",
            "name",
            "order"
        ],

        "Refund / cancellation": [
            "refund",
            "cancel",
            "cancellation",
            "money back",
            "credit"
        ],

        "Product issue / troubleshooting": [
            "not working",
            "failed",
            "problem",
            "issue",
            "broken",
            "error",
            "download"
        ],
    }

    hits = []

    for theme, keywords in theme_rules.items():
        score = sum(
            text.count(k)
            for k in keywords
        )

        if score:
            hits.append(
                (theme, score)
            )

    return [
        theme
        for theme, _ in sorted(
            hits,
            key=lambda x: (-x[1], x[0])
        )[:4]
    ]


def coaching_brief(row, ticket_subset):
    themes = extract_themes(
        ticket_subset.head(200)
    )

    theme_text = (
        ", ".join(themes)
        if themes
        else "no dominant operational theme found"
    )

    notes = (
        ticket_subset["agent_notes"]
        .dropna()
        .astype(str)
        .head(3)
        .tolist()
    )

    return f"""### Coaching brief — {row['name']} ({row['agent_id']})

**Why flagged:** CSAT **{row['csat']:.2f}**, median handle time **{format_minutes(row['median_handle_min'])}**, and SLA breach rate **{row['sla_rate']:.1%}** across **{int(row['tickets'])} tickets** ({int(row['csat_responses'])} CSAT responses).

**Observed ticket themes:** {theme_text}.

**Recommended coaching focus:** review a small sample of low-CSAT tickets first; check whether the issue is response speed, resolution quality, or queue/process complexity before attributing the result to the individual.

**Evidence rule:** do not treat missing CSAT as a zero. Tier 2 is excluded from this ranking. Structural queues such as Returns/Logistics should be reviewed with their operating context.

**Sample agent notes:** {' | '.join(notes) if notes else 'No notes available.'}
"""


st.title(
    "🎧 Vireo Audio — Support Performance Coach"
)

st.caption(
    "Evidence-first Tier 1 coaching dashboard • "
    "Jan 2025–Jun 2026 ticket data"
)


with st.sidebar:
    st.header("Data")

    uploaded_t = st.file_uploader(
        "tickets.csv",
        type="csv"
    )

    uploaded_a = st.file_uploader(
        "agents.csv",
        type="csv"
    )

    t, agents = load_data(
        uploaded_t,
        uploaded_a
    )

    st.divider()

    st.header("Analysis window")

    default_start = max(
        pd.Timestamp("2026-01-01"),
        t["created"].min().normalize()
    )

    start = st.date_input(
        "Start",
        value=default_start.date()
    )

    end = st.date_input(
        "End (exclusive)",
        value=pd.Timestamp("2026-07-01").date()
    )

    st.divider()

    st.info(
        "Tier 1 = Chat, Email, and Voice Frontline. "
        "Tier 2 and operational teams "
        "(Logistics, Billing, Returns Desk) are excluded. "
        "CSAT blanks are excluded from averages. "
        "Legacy resolution timestamps are shifted +5:30 "
        "for handle-time calculation."
    )


x, all_metrics, eligible = build_metrics(
    t,
    start,
    pd.Timestamp(end)
)


st.subheader("1. Executive outcome")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Tier 1 tickets",
    f"{len(x):,}"
)

col2.metric(
    "SLA breach rate",
    f"{x.sla_breach.mean():.1%}"
)

col3.metric(
    "SLA breaches",
    f"{int(x.sla_breach.sum()):,}"
)

col4.metric(
    "SLA credits",
    f"₹{int(x.sla_breach.sum() * SLA_CREDIT):,}"
)


st.markdown(
    "**Proposed business goal:** reduce Tier 1 "
    "first-response SLA breaches by **20% relative**. "
    "In Jan–Jun 2026, the strict Tier 1 baseline is "
    "**9.2% (260 breaches / 2,840 tickets)**. "
    "At ~650 tickets/week, moving to about **7.3%** "
    "avoids approximately **₹54,000 per quarter** "
    "in ₹350 SLA credits."
)


st.subheader(
    "2. Bottom-ten coaching candidates"
)

st.caption(
    "Strict Tier 1 only (Chat, Email, Voice Frontline). "
    "Peer-normalized within team. "
    "Score = 50% CSAT risk + 30% handle-time risk "
    "+ 20% SLA-breach risk. "
    "Minimum 30 CSAT responses and 30 tickets."
)


show = eligible.head(10).copy()

show["CSAT"] = show["csat"].map(
    lambda v: f"{v:.2f}"
)

show["Median handle"] = show[
    "median_handle_min"
].map(format_minutes)

show["SLA breach"] = show[
    "sla_rate"
].map(
    lambda v: f"{v:.1%}"
)

show["Risk score"] = show[
    "risk_score"
].map(
    lambda v: f"{v:.3f}"
)

show = show[
    [
        "agent_id",
        "name",
        "team",
        "tickets",
        "csat_responses",
        "CSAT",
        "Median handle",
        "SLA breach",
        "Risk score"
    ]
]

st.dataframe(
    show,
    use_container_width=True,
    hide_index=True
)


st.subheader(
    "3. Investigate one agent"
)

if not eligible.empty:

    options = [
        f"{r.agent_id} — {r.name}"
        for r in eligible.itertuples()
    ]

    selected = st.selectbox(
        "Select candidate",
        options
    )

    selected_id = selected.split(
        " — "
    )[0]

    row = eligible[
        eligible.agent_id == selected_id
    ].iloc[0]

    agent_tickets = x[
        x.agent_id == selected_id
    ].copy()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "CSAT",
        f"{row.csat:.2f}"
    )

    c2.metric(
        "Median handle",
        format_minutes(
            row.median_handle_min
        )
    )

    c3.metric(
        "SLA breach",
        f"{row.sla_rate:.1%}"
    )

    c4.metric(
        "Transfers",
        f"{int(row.transfers)}"
    )

    if st.button(
        "Generate evidence-based coaching brief",
        type="primary"
    ):
        st.markdown(
            coaching_brief(
                row,
                agent_tickets
            )
        )


st.subheader(
    "4. Proof / quality checks"
)

q1, q2, q3 = st.columns(3)

q1.metric(
    "Agents eligible",
    f"{len(eligible)}"
)

q2.metric(
    "CSAT responses",
    f"{int(x.csat_score.notna().sum()):,}"
)

q3.metric(
    "Missing first responses",
    f"{int(x.first_response.isna().sum()):,}"
)


st.markdown(
    "**Known failure cases / cautions:** "
    "auto-closed tickets can affect attendance; "
    "Returns and Logistics have structurally different work; "
    "Tier 2 is excluded; and the policy says missing CSAT "
    "must not be treated as zero. Review flagged tickets "
    "before using the list for training or bonus decisions."
)


st.download_button(
    "Download bottom-10 CSV",
    data=show.to_csv(
        index=False
    ).encode("utf-8"),
    file_name="vireo_bottom10.csv",
    mime="text/csv",
)