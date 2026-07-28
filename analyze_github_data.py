"""
GitHub Repo Growth Analytics — Analysis Script
------------------------------------------------
Loads the raw CSVs into a local SQLite DB, aggregates with SQL, then uses
pandas/scipy to test what actually correlates with star count:
  - commit consistency (avg weekly commits, or coefficient of variation)
  - issue responsiveness (avg time-to-close)
  - description/docs quality proxy
  - repo age

OUTPUT:
- github_analytics.db     -> SQLite DB with raw + aggregated tables
- analysis_summary.csv    -> one row per repo with all features + stars
- Prints correlation results and a plain-English summary to the console

SETUP:
  pip install pandas scipy matplotlib
"""

import sqlite3
import pandas as pd
from scipy import stats
from datetime import datetime

DB_PATH = "github_analytics.db"


def load_csvs_to_sqlite():
    conn = sqlite3.connect(DB_PATH)

    repos = pd.read_csv("raw_repos.csv")
    commits = pd.read_csv("raw_commit_activity.csv")
    issues = pd.read_csv("raw_issues.csv")

    repos.to_sql("repos", conn, if_exists="replace", index=False)
    commits.to_sql("commit_activity", conn, if_exists="replace", index=False)
    issues.to_sql("issues", conn, if_exists="replace", index=False)

    conn.close()
    print(f"Loaded {len(repos)} repos, {len(commits)} commit-weeks, "
          f"{len(issues)} issues into {DB_PATH}")


def build_feature_table():
    """SQL: aggregate commit activity and issue responsiveness per repo,
    then join onto repo-level stats to build one analysis-ready table."""
    conn = sqlite3.connect(DB_PATH)

    query = """
    WITH commit_agg AS (
        SELECT
            owner,
            repo,
            AVG(commits) AS avg_weekly_commits,
            -- consistency: lower stdev relative to mean = more consistent
            CASE WHEN AVG(commits) > 0
                 THEN (
                    SQRT(AVG(commits * commits) - AVG(commits) * AVG(commits))
                    / AVG(commits)
                 )
                 ELSE NULL END AS commit_variability
        FROM commit_activity
        GROUP BY owner, repo
    ),
    issue_agg AS (
        SELECT
            owner,
            repo,
            COUNT(*) AS closed_issue_count,
            AVG(
                (julianday(closed_at) - julianday(created_at))
            ) AS avg_days_to_close
        FROM issues
        WHERE closed_at IS NOT NULL
        GROUP BY owner, repo
    )
    SELECT
        r.full_name,
        r.stars,
        r.forks,
        r.open_issues,
        r.language,
        r.created_at,
        r.description_length,
        r.has_wiki,
        c.avg_weekly_commits,
        c.commit_variability,
        i.closed_issue_count,
        i.avg_days_to_close
    FROM repos r
    LEFT JOIN commit_agg c ON r.owner = c.owner AND r.repo = c.repo
    LEFT JOIN issue_agg i ON r.owner = i.owner AND r.repo = i.repo
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Normalize stars by repo age so a 5-year-old and 6-month-old repo
    # are comparable -- this is the "does growth rate matter" fix.
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["age_days"] = (pd.Timestamp.utcnow().tz_localize(None) - df["created_at"].dt.tz_localize(None)).dt.days
    df["stars_per_day"] = df["stars"] / df["age_days"].clip(lower=1)

    df.to_csv("analysis_summary.csv", index=False)
    print(f"Built feature table with {len(df)} repos -> analysis_summary.csv")
    return df


def run_correlations(df):
    features = {
        "avg_weekly_commits": "Commit frequency",
        "commit_variability": "Commit inconsistency (higher = less consistent)",
        "avg_days_to_close": "Issue response time (days)",
        "description_length": "Description/docs length (proxy for doc quality)",
        "age_days": "Repo age",
    }

    print("\n" + "=" * 60)
    print("CORRELATION WITH stars_per_day (normalized growth)")
    print("=" * 60)

    results = []
    for col, label in features.items():
        sub = df[[col, "stars_per_day"]].dropna()
        if len(sub) < 10:
            continue
        r, p = stats.pearsonr(sub[col], sub["stars_per_day"])
        results.append((label, r, p, len(sub)))
        sig = "significant (p<0.05)" if p < 0.05 else "not significant"
        print(f"{label:45s} r={r:+.3f}  p={p:.4f}  n={len(sub)}  [{sig}]")

    print("\nInterpretation notes:")
    print("- r close to 0 = weak/no linear relationship")
    print("- r closer to +1 or -1 = stronger relationship")
    print("- p < 0.05 = unlikely to be due to chance, worth reporting")
    print("- This is correlation, not causation -- say that explicitly")
    print("  in your writeup. It's a more credible claim, not a weaker one.")

    return results


if __name__ == "__main__":
    load_csvs_to_sqlite()
    df = build_feature_table()
    run_correlations(df)
