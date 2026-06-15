from __future__ import annotations

import streamlit as st


def apply_dark_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --dm-bg: #0b0f17;
            --dm-surface: #111827;
            --dm-surface-2: #172033;
            --dm-border: #2a3548;
            --dm-text: #e5e7eb;
            --dm-muted: #9ca3af;
            --dm-accent: #38bdf8;
        }

        .stApp {
            background: var(--dm-bg);
            color: var(--dm-text);
        }

        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3, h4, h5, h6, p, label, span {
            color: var(--dm-text);
        }

        [data-testid="stCaptionContainer"] {
            color: var(--dm-muted);
        }

        div[data-testid="stMetric"] {
            border: 1px solid var(--dm-border);
            border-radius: 6px;
            padding: 0.8rem 0.9rem;
            background: var(--dm-surface);
        }

        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--dm-text);
        }

        .dm-badge {
            border: 1px solid;
            border-radius: 6px;
            padding: 0.45rem 0.6rem;
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: center;
            background: var(--dm-surface);
            min-height: 2.4rem;
        }

        .dm-badge span {
            color: var(--dm-muted);
            font-size: 0.82rem;
        }

        .dm-badge strong {
            font-size: 0.9rem;
            font-weight: 650;
        }

        .dm-panel {
            border: 1px solid var(--dm-border);
            border-radius: 6px;
            padding: 0.9rem;
            background: var(--dm-surface);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 1.35rem !important;
            border-bottom: 1px solid var(--dm-border);
        }

        div[data-testid="stTabs"] div[role="tablist"] {
            gap: 1.35rem !important;
        }

        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border-radius: 6px 6px 0 0;
            color: var(--dm-muted);
        }

        div[data-testid="stTabs"] button[role="tab"] {
            padding: 0.65rem 1.05rem !important;
            margin-right: 0.2rem !important;
            min-width: fit-content;
        }

        div[data-testid="stTabs"] button[role="tab"] p {
            white-space: nowrap;
        }

        .stTabs [aria-selected="true"] {
            color: var(--dm-text);
            border-bottom: 2px solid var(--dm-accent);
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid var(--dm-border);
            border-radius: 6px;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 6px;
        }

        .dm-scan-or {
            min-height: 2.4rem;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--dm-muted);
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0;
            text-transform: uppercase;
        }

        .dm-index-scroll {
            width: 100%;
            border: 1px solid var(--dm-border);
            border-radius: 6px;
            background: var(--dm-surface);
        }

        .dm-index-table {
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
            font-size: 0.9rem;
        }

        .dm-index-table th:nth-child(1),
        .dm-index-table td:nth-child(1) {
            width: 18%;
        }

        .dm-index-table th:nth-child(2),
        .dm-index-table td:nth-child(2) {
            width: 12%;
        }

        .dm-index-table th:nth-child(n+3):nth-child(-n+6),
        .dm-index-table td:nth-child(n+3):nth-child(-n+6) {
            width: 9%;
        }

        .dm-index-table th:nth-child(n+7),
        .dm-index-table td:nth-child(n+7) {
            width: 6%;
        }

        .dm-index-table th {
            text-align: left;
            color: var(--dm-muted);
            font-weight: 650;
            padding: 0.7rem 0.75rem;
            border-bottom: 1px solid var(--dm-border);
            background: #0f172a;
            white-space: nowrap;
        }

        .dm-index-table td {
            padding: 0.62rem 0.75rem;
            border-bottom: 1px solid rgba(42, 53, 72, 0.7);
            color: var(--dm-text);
            vertical-align: middle;
        }

        .dm-index-table tr:last-child td {
            border-bottom: 0;
        }

        .dm-acquisition-cell {
            font-weight: 650;
            color: #f8fafc !important;
            white-space: nowrap;
        }

        .dm-status-pill {
            display: inline-block;
            width: 100%;
            max-width: 6.6rem;
            text-align: center;
            border-radius: 999px;
            padding: 0.22rem 0.55rem;
            font-size: 0.78rem;
            font-weight: 750;
            border: 1px solid transparent;
            white-space: nowrap;
        }

        .dm-status-complete {
            background: rgba(34, 197, 94, 0.18);
            border-color: rgba(34, 197, 94, 0.38);
            color: #86efac;
        }

        .dm-status-warning {
            background: rgba(245, 158, 11, 0.2);
            border-color: rgba(245, 158, 11, 0.42);
            color: #fcd34d;
        }

        .dm-status-partial {
            background: rgba(59, 130, 246, 0.18);
            border-color: rgba(59, 130, 246, 0.36);
            color: #93c5fd;
        }

        .dm-status-error {
            background: rgba(244, 63, 94, 0.2);
            border-color: rgba(244, 63, 94, 0.42);
            color: #fda4af;
        }

        .dm-status-not-started,
        .dm-status-unknown {
            background: rgba(148, 163, 184, 0.14);
            border-color: rgba(148, 163, 184, 0.28);
            color: #cbd5e1;
        }

        .dm-count-warning {
            color: #fcd34d;
            font-weight: 750;
        }

        .dm-count-with-details {
            cursor: help;
            display: inline-flex;
            align-items: center;
            position: relative;
            text-decoration: underline dotted rgba(252, 211, 77, 0.7);
            text-underline-offset: 0.18rem;
        }

        .dm-count-with-details:focus {
            outline: 1px solid rgba(252, 211, 77, 0.55);
            outline-offset: 0.18rem;
            border-radius: 3px;
        }

        .dm-count-tooltip {
            position: absolute;
            left: 0;
            top: calc(100% + 0.45rem);
            z-index: 20;
            width: max-content;
            min-width: 16rem;
            max-width: min(30rem, 72vw);
            padding: 0.55rem 0.7rem;
            border: 1px solid rgba(245, 158, 11, 0.42);
            border-radius: 6px;
            background: #111827;
            box-shadow: 0 0.7rem 1.6rem rgba(0, 0, 0, 0.32);
            opacity: 0;
            pointer-events: none;
            transform: translateY(-0.15rem);
            transition: opacity 120ms ease, transform 120ms ease;
            visibility: hidden;
        }

        .dm-count-with-details:hover .dm-count-tooltip,
        .dm-count-with-details:focus .dm-count-tooltip {
            opacity: 1;
            transform: translateY(0);
            visibility: visible;
        }

        .dm-count-tooltip-line {
            display: block;
            color: #e5e7eb;
            font-size: 0.78rem;
            font-weight: 500;
            line-height: 1.35;
            padding-left: 0.85rem;
            text-indent: -0.85rem;
            white-space: normal;
        }

        .dm-count-tooltip-line + .dm-count-tooltip-line {
            margin-top: 0.35rem;
        }

        .dm-count-muted,
        .dm-muted {
            color: var(--dm-muted);
        }

        .dm-path-cell {
            display: inline-block;
            max-width: 18rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: #cbd5e1;
        }

        .dm-presence-ok,
        .dm-presence-missing {
            display: inline-block;
            width: 100%;
            max-width: 4.6rem;
            text-align: center;
            border-radius: 999px;
            padding: 0.18rem 0.45rem;
            font-size: 0.76rem;
            font-weight: 700;
            white-space: nowrap;
        }

        .dm-presence-ok {
            background: rgba(20, 184, 166, 0.16);
            border: 1px solid rgba(20, 184, 166, 0.35);
            color: #5eead4;
        }

        .dm-presence-missing {
            background: rgba(148, 163, 184, 0.12);
            border: 1px solid rgba(148, 163, 184, 0.22);
            color: #cbd5e1;
        }

        .dm-export-spacer {
            height: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
