"""
Streamlit dashboard for immune cell population analysis.
Run: streamlit run dashboard.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import (
    POPULATIONS,
    build_frequency_table,
    compare_responders,
    compute_avg_bcells_melanoma_male_responders,
    fetch_baseline_melanoma_samples,
    fetch_melanoma_miraclib_pbmc,
    summarize_baseline_subset,
)
from load_data import DB_PATH, get_connection, load_all

RESPONSE_COLORS = {"yes": "#4CAF50", "no": "#F44336"}
SEX_COLORS = {"M": "#2196F3", "F": "#E91E63"}

st.set_page_config(page_title="Teiko – Immune Cell Analysis", page_icon="🔬", layout="wide")


@st.cache_resource
def _init_db():
    if not DB_PATH.exists():
        load_all()


_init_db()


def _get_conn() -> st.connection:
    """Fresh connection per call -- avoids SQLite cross-thread errors."""
    return get_connection()


st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", [
    "Overview",
    "Part 2 – Frequency Table",
    "Part 3 – Statistical Analysis",
    "Part 4 – Subset Analysis",
])


def _count(table: str) -> int:
    return pd.read_sql(f"SELECT COUNT(*) AS n FROM {table}", _get_conn()).iloc[0, 0]


def _render_overview() -> None:
    st.title("Teiko Technical Assignment – Dashboard")
    st.markdown(
        "Interactive view of immune cell population analysis for "
        "**Bob Loblaw's clinical trial data**. Use the **sidebar** to navigate."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Subjects", f"{_count('subjects'):,}")
    col2.metric("Samples", f"{_count('samples'):,}")
    col3.metric("Cell Count Rows", f"{_count('cell_counts'):,}")

    st.divider()
    st.subheader("Submission Question 1")
    avg_b = compute_avg_bcells_melanoma_male_responders(_get_conn())
    st.success(
        f"Average B-cell count for **melanoma males** who are **responders** "
        f"at **time = 0**: **{avg_b}**"
    )


def _render_frequency_table() -> None:
    st.title("Part 2 – Cell Population Relative Frequencies")

    @st.cache_data
    def _load():
        return build_frequency_table(get_connection())

    freq_df = _load()

    with st.expander("Filters", expanded=True):
        c1, c2 = st.columns(2)
        sample_query = c1.text_input("Search sample ID (contains)")
        selected_pops = c2.multiselect("Populations", options=POPULATIONS, default=POPULATIONS)

    filtered = freq_df[freq_df["population"].isin(selected_pops)]
    if sample_query:
        filtered = filtered[filtered["sample"].str.contains(sample_query)]

    st.dataframe(filtered, width="stretch", height=500)
    st.caption(f"Showing {len(filtered):,} of {len(freq_df):,} rows")

    st.subheader("Percentage Distribution by Population")
    fig = px.box(
        freq_df, x="population", y="percentage", color="population",
        labels={"percentage": "Relative Frequency (%)", "population": "Cell Population"},
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")


def _render_statistical_analysis() -> None:
    st.title("Part 3 – Responders vs Non-Responders")
    st.markdown(
        "Comparing cell population relative frequencies for **melanoma PBMC** "
        "patients receiving **miraclib**."
    )

    @st.cache_data
    def _load():
        return fetch_melanoma_miraclib_pbmc(get_connection())

    mel_df = _load()

    st.subheader("Boxplots – Relative Frequency by Response")
    for pop in POPULATIONS:
        fig = px.box(
            mel_df[mel_df["population"] == pop],
            x="response", y="percentage", color="response",
            category_orders={"response": ["yes", "no"]},
            color_discrete_map=RESPONSE_COLORS,
            labels={"percentage": "Relative Frequency (%)", "response": "Response"},
            title=pop.replace("_", " ").title(),
        )
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, width="stretch")

    st.subheader("Mann-Whitney U Test Results")
    stat_df = compare_responders(mel_df)
    st.dataframe(
        stat_df.style.map(
            lambda v: "background-color: #c8e6c9" if v else "",
            subset=["significant"],
        ),
        width="stretch",
    )
    st.markdown(
        "**Conclusion:** Populations marked *True* show a statistically significant "
        "difference (p < 0.05) between responders and non-responders."
    )


def _render_subset_analysis() -> None:
    st.title("Part 4 – Baseline Melanoma PBMC Subset")

    @st.cache_data
    def _load():
        return fetch_baseline_melanoma_samples(get_connection())

    baseline = _load()

    st.subheader("Task 1: Baseline Samples")
    st.markdown(
        f"Melanoma PBMC samples at **time = 0** treated with **miraclib**: "
        f"**{len(baseline)}** samples"
    )
    st.dataframe(baseline, width="stretch", height=400)

    st.subheader("Task 2: Summary Statistics")
    summary = summarize_baseline_subset(baseline)
    col1, col2, col3 = st.columns(3)

    with col1:
        sp = summary["samples_per_project"].reset_index()
        sp.columns = ["Project", "Samples"]
        st.markdown("**Samples per Project**")
        st.dataframe(sp, width="stretch", hide_index=True)
        fig = px.bar(sp, x="Project", y="Samples", color="Project", title="Samples per Project")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")

    with col2:
        rc = summary["response_counts"].reset_index()
        rc.columns = ["Response", "Subjects"]
        st.markdown("**Responders vs Non-Responders**")
        st.dataframe(rc, width="stretch", hide_index=True)
        st.plotly_chart(
            px.pie(rc, names="Response", values="Subjects", title="Response Distribution",
                   color="Response", color_discrete_map=RESPONSE_COLORS),
            width="stretch",
        )

    with col3:
        sc = summary["sex_counts"].reset_index()
        sc.columns = ["Sex", "Subjects"]
        st.markdown("**Males vs Females**")
        st.dataframe(sc, width="stretch", hide_index=True)
        st.plotly_chart(
            px.pie(sc, names="Sex", values="Subjects", title="Sex Distribution",
                   color="Sex", color_discrete_map=SEX_COLORS),
            width="stretch",
        )


PAGES = {
    "Overview": _render_overview,
    "Part 2 – Frequency Table": _render_frequency_table,
    "Part 3 – Statistical Analysis": _render_statistical_analysis,
    "Part 4 – Subset Analysis": _render_subset_analysis,
}

PAGES[page]()
