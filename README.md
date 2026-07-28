# GitHub Repo Growth Analytics

**What drives a repository's star growth — and what just looks like it does?**

A data analytics project examining 149 GitHub repositories to test whether commit frequency,
issue responsiveness, and documentation quality actually predict star growth, or whether
those relationships are just artifacts of how old a project is.

## Key Finding

After controlling for repository age using multiple regression, **commit frequency is an
independent predictor of normalized star growth** (p = 0.002). Documentation quality and
issue response time, which appeared significant in an initial single-variable correlation
analysis, turned out to be **confounded by repo age** — younger repos simply tend to have
both more active commits *and* better documentation, which made documentation look
predictive until age was properly controlled for.

| Feature | Simple correlation | Significant after controlling for age? |
|---|---|---|
| Commit frequency | r = +0.176, p = 0.049 | **Yes** (p = 0.002) |
| Description length (docs proxy) | r = +0.218, p = 0.0075 | No (p = 0.198) — confounded by age |
| Issue response time | r = -0.162, p = 0.050 | No (p = 0.290) |
| Repo age | r = -0.373, p < 0.0001 | Yes (p < 0.001) — dominant factor |

## Why This Matters

A naive analysis would have reported "better documentation drives growth" and stopped there.
Controlling for the age confound overturned that conclusion — which is the actual point of
the project: catching a plausible-but-wrong finding before it becomes a business
recommendation.

## Methodology

1. **Data collection** — Pulled repo metadata, weekly commit activity (last 52 weeks), and
   closed-issue timestamps for 149 repositories via the GitHub REST API.
2. **Storage & aggregation** — Loaded raw data into SQLite; used SQL (CTEs, joins) to compute
   per-repo aggregates: average weekly commits, commit variability, average issue close time.
3. **Feature engineering** — Normalized star count by repo age (`stars_per_day`) so repos of
   different ages are comparable.
4. **Exploratory analysis** — Ran single-variable Pearson correlations against normalized
   growth.
5. **Confound check** — Ran a multiple linear regression (OLS) with all features together to
   isolate each one's independent effect while holding repo age constant.
6. **Diagnostics** — Checked regression residuals; found heavy right-skew (a few viral repos
   dominating), fixed with a log-transform of the target variable, which improved model fit
   (R² rose from 0.16 to 0.63) and normalized the residuals.

## Tech Stack

- **Python** — `requests` (API calls), `pandas` (data wrangling), `scipy` / `statsmodels`
  (statistical testing)
- **SQL** — SQLite, used for aggregation via CTEs and joins
- **GitHub REST API** — data source

## Repository Structure

```
├── collect_github_data.py     # Pulls repo, commit, and issue data from GitHub API
├── analyze_github_data.py     # Loads data into SQLite, runs SQL aggregation + correlations
├── regression_analysis.py     # Multiple regression controlling for age confound
├── raw_repos.csv              # Raw repo-level data (generated)
├── raw_commit_activity.csv    # Raw weekly commit data (generated)
├── raw_issues.csv             # Raw issue data (generated)
├── analysis_summary.csv       # Final feature table used for regression (generated)
├── github_analytics.db        # SQLite database (generated)
└── README.md
```

## How to Reproduce

```bash
pip install requests pandas scipy statsmodels

# 1. Set your GitHub personal access token (no billing/card required)
$env:GITHUB_TOKEN="your_token_here"      # PowerShell
# export GITHUB_TOKEN="your_token_here"  # macOS/Linux

# 2. Collect data (edit SEARCH_QUERIES in the script for your chosen niche first)
python collect_github_data.py

# 3. Load into SQLite and run correlation analysis
python analyze_github_data.py

# 4. Run the confound-controlled regression
python regression_analysis.py
```

## Limitations

- This is observational data — correlation, not causation. The regression controls for one
  confound (age) but not others; unmeasured factors (e.g. what the repo actually does, marketing
  outside GitHub) aren't captured.
- The regression's condition number flags some multicollinearity between features, and the
  Durbin-Watson statistic suggests mild autocorrelation in residuals — noted rather than
  hidden.
- Sample limited to 149 repos across a handful of search queries; not a random sample of
  GitHub as a whole.

## Author's Note

Built as a portfolio project to demonstrate the full data analytics lifecycle: sourcing data
from an API, cleaning and aggregating with SQL, exploratory statistics, and — most
importantly — catching and correcting a confounded finding rather than reporting the first
significant correlation found. 
