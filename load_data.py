"""
Database initialization and CSV ingestion.

Normalizes cell-count.csv into three tables (subjects, samples, cell_counts)
in an SQLite database. See README.md for schema rationale.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "teiko.db"
CSV_PATH = Path(__file__).parent / "cell-count.csv"

POPULATION_COLUMNS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subjects (
    subject_id  TEXT PRIMARY KEY,
    project     TEXT NOT NULL,
    condition   TEXT NOT NULL,
    age         INTEGER,
    sex         TEXT
);

CREATE TABLE IF NOT EXISTS samples (
    sample_id                 TEXT PRIMARY KEY,
    subject_id                TEXT NOT NULL,
    sample_type               TEXT NOT NULL,
    treatment                 TEXT,
    response                  TEXT,
    time_from_treatment_start INTEGER,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS cell_counts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id  TEXT NOT NULL,
    population TEXT NOT NULL,
    count      INTEGER NOT NULL,
    FOREIGN KEY (sample_id) REFERENCES samples(sample_id),
    UNIQUE(sample_id, population)
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _create_database(db_path: Path) -> sqlite3.Connection:
    if db_path.exists():
        db_path.unlink()
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    return conn


def _insert_subjects(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    (
        df[["subject", "project", "condition", "age", "sex"]]
        .drop_duplicates(subset=["subject"])
        .rename(columns={"subject": "subject_id"})
        .to_sql("subjects", conn, if_exists="append", index=False)
    )


def _insert_samples(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    (
        df[["sample", "subject", "sample_type", "treatment", "response",
            "time_from_treatment_start"]]
        .drop_duplicates(subset=["sample"])
        .rename(columns={"sample": "sample_id", "subject": "subject_id"})
        .to_sql("samples", conn, if_exists="append", index=False)
    )


def _insert_cell_counts(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    """Wide-to-long melt so each population becomes its own row."""
    (
        df.melt(
            id_vars=["sample"],
            value_vars=POPULATION_COLUMNS,
            var_name="population",
            value_name="count",
        )
        .rename(columns={"sample": "sample_id"})
        .to_sql("cell_counts", conn, if_exists="append", index=False)
    )


def load_all(
    db_path: Path = DB_PATH,
    csv_path: Path = CSV_PATH,
) -> sqlite3.Connection:
    """Read cell-count.csv, create a fresh SQLite DB, and return the connection."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    conn = _create_database(db_path)

    _insert_subjects(conn, df)
    _insert_samples(conn, df)
    _insert_cell_counts(conn, df)
    conn.commit()

    row_counts = {
        t: pd.read_sql(f"SELECT COUNT(*) AS n FROM {t}", conn).iloc[0, 0]
        for t in ("subjects", "samples", "cell_counts")
    }
    log.info("Database created at %s  %s", db_path, row_counts)
    return conn


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_all()
