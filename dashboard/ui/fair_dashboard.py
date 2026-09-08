from __future__ import annotations

from html import escape
import streamlit as st


def inject_platform_css() -> None:
    st.markdown(
        """
        <style>
        :root { --ink:#172033; --muted:#687386; --line:#E5EAF0; --accent:#0F766E; --soft:#F1F8F7; --warn:#A16207; --danger:#B42318; }
        .block-container {max-width: 1320px; padding-top: 1.7rem; padding-bottom: 5rem;}
        [data-testid="stSidebar"] {background:#111827; border-right:0;}
        [data-testid="stSidebar"] * {color:#F8FAFC;}
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {color:#94A3B8 !important;}
        [data-testid="stSidebar"] hr {border-color:#273244;}
        .platform-hero {padding:2.1rem 2.25rem; border:1px solid var(--line); border-radius:24px; background:linear-gradient(135deg,#FFFFFF 0%,#F2FAF8 65%,#EEF5FF 100%); margin:0 0 1.4rem 0; box-shadow:0 12px 36px rgba(23,32,51,.05);}
        .kicker {font-size:.75rem; letter-spacing:.14em; text-transform:uppercase; font-weight:800; color:var(--accent);}
        .platform-hero h1 {font-size:2.35rem; letter-spacing:-.035em; line-height:1.08; margin:.45rem 0 .65rem; color:var(--ink);}
        .platform-hero p {font-size:1.03rem; line-height:1.65; color:#596579; max-width:920px; margin:0;}
        .surface {border:1px solid var(--line); border-radius:18px; background:#fff; padding:1.2rem 1.25rem; box-shadow:0 6px 18px rgba(23,32,51,.035);}
        .mini-label {font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; font-weight:800; color:#7B8799;}
        .big-state {font-size:1.42rem; font-weight:800; color:var(--ink); margin:.4rem 0 .2rem;}
        .subtle {color:var(--muted); font-size:.9rem;}
        .status-ready,.status-partial,.status-review,.status-neutral {display:inline-block;padding:.28rem .62rem;border-radius:999px;font-size:.76rem;font-weight:800;letter-spacing:.02em;}
        .status-ready {background:#E8F7F1;color:#087A55}.status-partial{background:#FFF6E6;color:#9A6700}.status-review{background:#FEECEC;color:#B42318}.status-neutral{background:#EEF2F7;color:#536174}
        .flow-number {font-size:.72rem;font-weight:800;color:var(--accent);letter-spacing:.1em;text-transform:uppercase}
        .flow-title {font-size:1.12rem;font-weight:800;color:var(--ink);margin:.35rem 0}
        .flow-copy {font-size:.9rem;color:var(--muted);line-height:1.5}
        .resource-chip {display:inline-block;background:#F3F6FA;border:1px solid #E5EAF0;border-radius:8px;padding:.25rem .48rem;margin:.15rem .2rem .15rem 0;font-size:.76rem;color:#506076;font-weight:650}
        div.stButton > button {border-radius:11px; font-weight:700;}
        div[data-testid="stFileUploader"] section {border-radius:14px; border-style:dashed;}
        [data-testid="stMetric"] {background:#fff;border:1px solid var(--line);padding:.85rem 1rem;border-radius:14px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str = "FAIR Acoustic Component Platform") -> None:
    st.markdown(
        f'<div class="platform-hero"><div class="kicker">{escape(eyebrow)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def status_class(status: str) -> str:
    if status in {"FAIR_READY", "ACCEPTABLE"}:
        return "status-ready"
    if status in {"PARTIALLY_FAIR", "STALE", "SEMANTICALLY_STALE", "AMBIGUOUS"}:
        return "status-partial"
    if status in {"INVALID", "BROKEN", "UNMATCHED", "MULTIPLE_CANDIDATES", "NOT_FINDABLE", "NOT_ACCESSIBLE", "NOT_INTEROPERABLE", "NOT_REUSABLE"}:
        return "status-review"
    return "status-neutral"


def badge(status: str) -> str:
    return f'<span class="{status_class(status)}">{escape(status)}</span>'


def render_fair_cards(result) -> None:
    columns = st.columns(4)
    for column, dimension in zip(columns, result.dimensions):
        passed = sum(item.passed for item in dimension.criteria)
        state = "Ready" if dimension.passed else "Needs work"
        css = "status-ready" if dimension.passed else "status-partial"
        column.markdown(
            f'<div class="surface"><div class="mini-label">{escape(dimension.name)}</div><div class="big-state">{dimension.score:.0%}</div><span class="{css}">{state}</span><div class="subtle" style="margin-top:.55rem">{passed}/{len(dimension.criteria)} criteria satisfied</div></div>',
            unsafe_allow_html=True,
        )


def empty_state(title: str, text: str) -> None:
    st.markdown(f'<div class="surface"><div class="big-state">{escape(title)}</div><div class="subtle">{escape(text)}</div></div>', unsafe_allow_html=True)
