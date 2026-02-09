"""
Analytical queries and statistical tests on the teiko.db database.

Covers relative frequency tables, responder vs non-responder comparisons,
and baseline subset exploration.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy import stats

from load_data import get_connection

log = logging.getLogger(__name__)

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]
SIGNIFICANCE_THRESHOLD = 0.05


def _attach_percentages(df: pd.DataFrame) -> pd.DataFrame:
    """Add total_count and percentage columns to a long-format cell-count frame."""
    totals = df.groupby("sample", as_index=False)["count"].sum().rename(columns={"count": "total_count"})
    df = df.merge(totals, on="sample")
    df["percentage"] = df["count"] / df["total_count"] * 100
    return df


def build_frequency_table(conn: sqlite3.Connection) -> pd.DataFrame:
    """Compute relative frequency of each population per sample."""
    df = pd.read_sql(
        "SELECT sample_id AS sample, population, count FROM cell_counts",
        conn,
    )
    return (
        _attach_percentages(df)
        [["sample", "total_count", "population", "count", "percentage"]]
        .sort_values(["sample", "population"])
        .reset_index(drop=True)
    )


def fetch_melanoma_miraclib_pbmc(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return per-population percentages for the melanoma PBMC miraclib cohort."""
    query = """
        SELECT
            cc.sample_id  AS sample,
            s.subject_id  AS subject,
            s.response,
            s.time_from_treatment_start,
            sub.sex,
            cc.population,
            cc.count
        FROM cell_counts cc
        JOIN samples s    ON cc.sample_id  = s.sample_id
        JOIN subjects sub ON s.subject_id  = sub.subject_id
        WHERE sub.condition  = 'melanoma'
          AND s.treatment    = 'miraclib'
          AND s.sample_type  = 'PBMC'
    """
    return _attach_percentages(pd.read_sql(query, conn))


def compare_responders(df: pd.DataFrame) -> pd.DataFrame:
    """Mann-Whitney U test per population: responders vs non-responders."""
    rows: list[dict[str, Any]] = []
    for pop in POPULATIONS:
        pop_df = df[df["population"] == pop]
        yes = pop_df.loc[pop_df["response"] == "yes", "percentage"]
        no = pop_df.loc[pop_df["response"] == "no", "percentage"]
        u, p = stats.mannwhitneyu(yes, no, alternative="two-sided")
        rows.append({
            "population": pop,
            "u_statistic": u,
            "p_value": p,
            "significant": p < SIGNIFICANCE_THRESHOLD,
        })
    return pd.DataFrame(rows)


def plot_response_boxplots(
    df: pd.DataFrame,
    save_path: Path | str | None = None,
) -> plt.Figure:
    """One boxplot per population comparing responders vs non-responders."""
    fig, axes = plt.subplots(1, len(POPULATIONS), figsize=(22, 5), sharey=False)
    for ax, pop in zip(axes, POPULATIONS):
        sns.boxplot(
            data=df[df["population"] == pop],
            x="response", y="percentage", hue="response",
            order=["yes", "no"], hue_order=["yes", "no"],
            palette={"yes": "#4CAF50", "no": "#F44336"},
            legend=False, ax=ax,
        )
        ax.set_title(pop.replace("_", " ").title())
        ax.set_xlabel("Response")
        ax.set_ylabel("Relative Frequency (%)")
    fig.suptitle("Melanoma PBMC – Miraclib: Responders vs Non-Responders", y=1.02)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        log.info("Boxplot saved to %s", save_path)
    return fig


def fetch_baseline_melanoma_samples(conn: sqlite3.Connection) -> pd.DataFrame:
    """Melanoma PBMC samples at baseline (time=0) treated with miraclib."""
    return pd.read_sql(
        """
        SELECT s.sample_id, s.subject_id, sub.project, sub.condition,
               s.treatment, s.response, sub.sex, s.time_from_treatment_start
        FROM samples s
        JOIN subjects sub ON s.subject_id = sub.subject_id
        WHERE sub.condition                = 'melanoma'
          AND s.sample_type                = 'PBMC'
          AND s.treatment                  = 'miraclib'
          AND s.time_from_treatment_start  = 0
        """,
        conn,
    )


def summarize_baseline_subset(baseline: pd.DataFrame) -> dict[str, pd.Series]:
    """Aggregate baseline samples by project, response, and sex."""
    subjects = baseline.drop_duplicates(subset=["subject_id"])
    return {
        "samples_per_project": baseline.groupby("project")["sample_id"].count(),
        "response_counts": subjects["response"].value_counts(),
        "sex_counts": subjects["sex"].value_counts(),
    }


def compute_avg_bcells_melanoma_male_responders(conn: sqlite3.Connection) -> float:
    """Average B-cell count for melanoma males who are responders at time=0."""
    result = pd.read_sql(
        """
        SELECT AVG(cc.count) AS avg_b_cell
        FROM cell_counts cc
        JOIN samples s    ON cc.sample_id  = s.sample_id
        JOIN subjects sub ON s.subject_id  = sub.subject_id
        WHERE sub.condition                = 'melanoma'
          AND sub.sex                      = 'M'
          AND s.response                   = 'yes'
          AND s.time_from_treatment_start  = 0
          AND cc.population                = 'b_cell'
        """,
        conn,
    )
    return round(result.iloc[0, 0], 2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    conn = get_connection()

    freq = build_frequency_table(conn)
    log.info("Frequency table: %d rows", len(freq))

    mel = fetch_melanoma_miraclib_pbmc(conn)
    log.info("Statistical tests:\n%s", compare_responders(mel).to_string(index=False))
    plot_response_boxplots(mel, save_path="boxplots.png")

    baseline = fetch_baseline_melanoma_samples(conn)
    log.info("Baseline melanoma PBMC miraclib samples: %d", len(baseline))

    summary = summarize_baseline_subset(baseline)
    for label, series in summary.items():
        log.info("%s:\n%s", label, series.to_string())

    log.info(
        "Question 1 – avg B cells (melanoma, male, responder, time=0): %s",
        compute_avg_bcells_melanoma_male_responders(conn),
    )
    conn.close()
