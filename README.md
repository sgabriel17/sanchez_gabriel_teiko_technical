# Teiko Technical Assignment – Immune Cell Population Analysis

A Python application that loads clinical trial immune cell data into a relational database, performs frequency and statistical analyses, and presents results through an interactive Streamlit dashboard.

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize the database (loads cell-count.csv into SQLite)
python load_data.py

# 3. Run the analysis (logs results to console, generates boxplots.png)
python analysis.py

# 4. Launch the interactive dashboard
streamlit run dashboard.py
```

The dashboard will open at **http://localhost:8501**.

### Running in GitHub Codespaces

```bash
# From the repository root:
pip install -r requirements.txt
python load_data.py
streamlit run dashboard.py --server.headless true
```

Codespaces will provide a forwarded URL for the Streamlit app.

---

## Project Structure

```
├── README.md                # This file
├── requirements.txt         # Python dependencies
├── cell-count.csv           # Input data (provided)
├── load_data.py             # Part 1 – Database schema & data loader
├── analysis.py              # Parts 2-4 – All analytical functions
├── dashboard.py             # Interactive Streamlit dashboard
├── teiko.db                 # Generated SQLite database (output)
├── boxplots.png             # Generated boxplot image (output)
└── Teiko_Technical_Assignment.md  # Assignment specification
```

### Design Rationale

The code is split into three modules with clear boundaries:

| Module | Responsibility |
|---|---|
| `load_data.py` | Schema creation and ETL – normalizes the CSV into SQLite. Public entry point: `load_all()`. Internal helpers are prefixed with `_`. |
| `analysis.py` | Analytical logic – frequency calculations, statistical tests, subset queries. Shared utilities (e.g. `_attach_percentages()`) are DRY-extracted. All output uses `logging`, not `print`. |
| `dashboard.py` | Presentation layer – each page is a standalone render function dispatched via a `PAGES` dict. Consumes `analysis.py` functions directly. |

This separation means the analytical logic can be used independently of the dashboard (e.g., from a notebook, a CLI, or a different frontend) and that the database layer is decoupled from the analysis.

---

## Database Schema

The CSV is normalized into three tables following Third Normal Form (3NF):

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   subjects   │       │     samples      │       │  cell_counts │
├──────────────┤       ├──────────────────┤       ├──────────────┤
│ subject_id PK│◄──────│ subject_id    FK │       │ id        PK │
│ project      │       │ sample_id     PK │◄──────│ sample_id FK │
│ condition    │       │ sample_type      │       │ population   │
│ age          │       │ treatment        │       │ count        │
│ sex          │       │ response         │       └──────────────┘
└──────────────┘       │ time_from_       │
                       │  treatment_start │
                       └──────────────────┘
```

### Tables

1. **`subjects`** – One row per patient. Stores demographics (age, sex) and clinical metadata (project, condition/indication).

2. **`samples`** – One row per biological sample. Each sample belongs to one subject. Stores sample-level attributes like type (PBMC), treatment, response, and time point.

3. **`cell_counts`** – One row per (sample, population) pair in **long format**. Stores the raw cell count for each of the five immune cell populations.

### Why This Design?

- **Normalization eliminates redundancy.** Subject metadata (age, sex, condition) is stored once per subject, not repeated across every sample row. This prevents update anomalies and reduces storage.

- **Long-format cell counts are extensible.** If new cell populations are added (e.g., `regulatory_t_cell`, `dendritic_cell`), no schema changes are needed – new rows are simply inserted into `cell_counts`. In a wide-format design, every new population would require an `ALTER TABLE ADD COLUMN`.

- **Scales to hundreds of projects and thousands of samples.** The normalized structure means queries can efficiently join only the tables they need. Adding indexes on `subject_id`, `sample_id`, `condition`, `treatment`, and `time_from_treatment_start` would further optimize query performance at scale.

- **Supports diverse analytics.** The relational structure makes it straightforward to write SQL for any combination of filters (by project, condition, treatment, time point, response, sex, etc.) and aggregations (counts, averages, frequencies) without reshaping the data.

---

## Analysis Summary

### Part 2 – Frequency Table

For each sample, the total cell count is computed by summing all five populations. The relative frequency of each population is then calculated as `(count / total_count) × 100`.

### Part 3 – Statistical Analysis

Filtered to **melanoma PBMC patients receiving miraclib**, the analysis compares relative frequencies between responders and non-responders using:

- **Boxplots** for visual comparison of each population's distribution
- **Mann-Whitney U tests** for statistical significance (α = 0.05)

**Result:** `cd4_t_cell` shows a statistically significant difference between responders and non-responders (p = 0.013).

### Part 4 – Subset Analysis

- **Task 1:** Identified **656** melanoma PBMC baseline (time=0) samples treated with miraclib.
- **Task 2:**
  - Samples per project: prj1 = 384, prj3 = 272
  - Responders: 331, Non-responders: 325
  - Males: 344, Females: 312

---

## Submission Answers

### Question 1
**Average B cells for melanoma males who are responders at time=0:** **10206.15**

---

## Dashboard

The interactive dashboard is built with [Streamlit](https://streamlit.io/) and includes four pages:

1. **Overview** – Key metrics and Question 1 answer
2. **Part 2** – Searchable/filterable frequency table with distribution chart
3. **Part 3** – Interactive boxplots and statistical test results
4. **Part 4** – Baseline subset explorer with summary charts
