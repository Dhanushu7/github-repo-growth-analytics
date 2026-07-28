"""
GitHub Repo Growth Analytics — Data Collection Script
--------------------------------------------------------
Pulls repo-level and activity-level data for repos in a chosen niche so
you can analyze what actually predicts star growth (docs quality? commit
frequency? issue responsiveness?) vs. what people assume matters.

SETUP:
1. pip install requests pandas
2. Create a personal access token (no billing, no card needed):
   GitHub -> Settings -> Developer settings -> Personal access tokens ->
   Tokens (classic) -> Generate new token -> no scopes needed for public
   data, just check nothing or "public_repo" if you want to be safe.
3. Set it as an env var: export GITHUB_TOKEN="ghp_xxxx"

OUTPUT:
- raw_repos.csv         -> one row per repo (stars, forks, age, language, etc.)
- raw_commit_activity.csv -> weekly commit counts per repo (last 52 weeks)
- raw_issues.csv        -> issue-level data (open/close times) for responsiveness

Run once for a baseline. Re-run every 1-2 weeks on the SAME repo list to
track star growth over time -- that's what turns this into a real growth
analysis instead of a single snapshot.
"""

import os
import csv
import time
from datetime import datetime
import requests

TOKEN = os.environ.get("GITHUB_TOKEN", "PASTE_YOUR_TOKEN_HERE")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
BASE_URL = "https://api.github.com"
RUN_DATE = datetime.utcnow().strftime("%Y-%m-%d")

# ---- 1. Define your search terms to discover repos in a niche ----------
# Mix a few related queries to get variety in size/age/popularity.
SEARCH_QUERIES = [
    "topic:cli language:python",
    "topic:react-components",
    "topic:developer-tools stars:>100",
    # add more queries relevant to your chosen niche
]
REPOS_PER_QUERY = 50   # GitHub search caps at 100 per page, 1000 results per query
MAX_REPOS_TOTAL = 150


def check_rate_limit():
    resp = requests.get(f"{BASE_URL}/rate_limit", headers=HEADERS).json()
    remaining = resp["resources"]["core"]["remaining"]
    if remaining < 20:
        reset = resp["resources"]["core"]["reset"]
        wait = max(0, reset - time.time())
        print(f"  Low on rate limit ({remaining} left). Sleeping {int(wait)}s...")
        time.sleep(wait + 5)


def search_repos(query, per_page=50):
    check_rate_limit()
    resp = requests.get(
        f"{BASE_URL}/search/repositories",
        headers=HEADERS,
        params={"q": query, "sort": "stars", "order": "desc", "per_page": per_page},
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def get_commit_activity(owner, repo):
    """Weekly commit counts for the last 52 weeks. GitHub sometimes returns
    202 while it computes stats in the background -- retry once."""
    check_rate_limit()
    url = f"{BASE_URL}/repos/{owner}/{repo}/stats/commit_activity"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 202:
        time.sleep(3)
        resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return []
    weeks = resp.json()
    return [{"owner": owner, "repo": repo, "week": w["week"], "commits": w["total"],
              "pulled_at": RUN_DATE} for w in weeks]


def get_issue_stats(owner, repo, max_issues=100):
    """Pull recent closed issues to measure responsiveness (time to close)."""
    check_rate_limit()
    resp = requests.get(
        f"{BASE_URL}/repos/{owner}/{repo}/issues",
        headers=HEADERS,
        params={"state": "closed", "per_page": max_issues, "sort": "updated"},
    )
    if resp.status_code != 200:
        return []
    rows = []
    for issue in resp.json():
        if "pull_request" in issue:  # skip PRs, keep real issues only
            continue
        rows.append({
            "owner": owner,
            "repo": repo,
            "issue_number": issue["number"],
            "created_at": issue["created_at"],
            "closed_at": issue["closed_at"],
            "comments": issue["comments"],
            "pulled_at": RUN_DATE,
        })
    return rows


def main():
    seen = set()
    repo_rows = []
    commit_rows = []
    issue_rows = []

    for query in SEARCH_QUERIES:
        print(f"Searching: {query}")
        items = search_repos(query, per_page=REPOS_PER_QUERY)

        for item in items:
            full_name = item["full_name"]
            if full_name in seen or len(seen) >= MAX_REPOS_TOTAL:
                continue
            seen.add(full_name)
            owner, repo = item["owner"]["login"], item["name"]

            print(f"  -> {full_name}")
            repo_rows.append({
                "full_name": full_name,
                "owner": owner,
                "repo": repo,
                "stars": item["stargazers_count"],
                "forks": item["forks_count"],
                "open_issues": item["open_issues_count"],
                "language": item["language"],
                "created_at": item["created_at"],
                "pushed_at": item["pushed_at"],
                "has_wiki": item["has_wiki"],
                "description_length": len(item["description"] or ""),
                "pulled_at": RUN_DATE,
            })

            commit_rows += get_commit_activity(owner, repo)
            issue_rows += get_issue_stats(owner, repo)

    write_csv("raw_repos.csv", repo_rows)
    write_csv("raw_commit_activity.csv", commit_rows)
    write_csv("raw_issues.csv", issue_rows)
    print(f"\nDone. {len(repo_rows)} repos, {len(commit_rows)} commit-weeks, "
          f"{len(issue_rows)} issues pulled.")


def write_csv(filename, rows):
    if not rows:
        return
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

# -------------------------------------------------------------------------
# NOTES:
# - README quality isn't in this script's fields yet -- fetch it separately
#   with GET /repos/{owner}/{repo}/readme (base64-decode the content) and
#   score it however you like (length, has code blocks, has badges, has
#   a table of contents, etc.) as a follow-up enrichment step.
# - "description_length" is included as a cheap README-quality proxy.
# - Authenticated requests get 5,000/hour; the check_rate_limit() function
#   self-throttles so you don't have to babysit it.
# - README content: GET /repos/{owner}/{repo}/readme, decode base64.
# -------------------------------------------------------------------------
