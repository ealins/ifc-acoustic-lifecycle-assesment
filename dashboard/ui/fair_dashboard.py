from __future__ import annotations

import streamlit as st


def inject_platform_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1280px; padding-top: 2rem; padding-bottom: 4rem;}
        [data-testid="stSidebar"] {border-right: 1px solid #e7eaf0;}
        .hero {padding: 2rem 2.2rem; border: 1px solid #e6e9ef; border-radius: 22px; background: linear-gradient(135deg,#ffffff 0%,#f3faf9 100%); margin-bottom: 1.4rem;}
        .eyebrow {font-size:.78rem; letter-spacing:.13em; text-transform:uppercase; font-weight:700; color:#0f766e;}
        .hero h1 {font-size:2.25rem; line-height:1.08; margin:.45rem 0 .65rem 0; color:#172033;}
        .hero p {font-size:1.05rem; color:#586174; max-width:850px;}
        .metric-card {padding:1.1rem 1.2rem; border:1px solid #e5e9ef; border-radius:16px; background:#fff; min-height:138px;}
        .metric-card .label {font-size:.76rem; text-transform:uppercase; letter-spacing:.09em; color:#697386; font-weight:700;}
        .metric-card .state {font-size:1.35rem; font-weight:750; color:#172033; margin:.4rem 0;}
        .metric-card .score {font-size:.88rem; color:#697386;}
        .section-card {padding:1.25rem; border:1px solid #e5e9ef; border-radius:18px; background:#fff;}
        .pill {display:inline-block; padding:.28rem .58rem; border-radius:999px; background:#edf8f6; color:#0f766e; font-size:.78rem; font-weight:700; margin-right:.3rem;}
        div.stButton > button[kind="primary"] {border-radius:12px; font-weight:700;}
        div[data-testid="stFileUploader"] {border-radius:16px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str = "FAIR Acoustic Component Platform") -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def render_fair_cards(result) -> None:
    dimensions = [
        ("Findable", result.findable),
        ("Accessible", result.accessible),
        ("Interoperable", result.interoperable),
        ("Reusable", result.reusable),
    ]
    cols = st.columns(4)
    for col, (label, dimension) in zip(cols, dimensions):
        passed = sum(dimension.checks.values())
        total = len(dimension.checks)
        icon = "✓" if dimension.passed else "!"
        state = "Ready" if dimension.passed else "Needs attention"
        col.markdown(
            f'<div class="metric-card"><div class="label">{label}</div><div class="state">{icon} {state}</div><div class="score">{passed}/{total} checks · {dimension.score:.0%}</div></div>',
            unsafe_allow_html=True,
        )
