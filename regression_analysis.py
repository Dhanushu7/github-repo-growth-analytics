"""
GitHub Repo Growth Analytics — Multiple Regression (controls for age)
-------------------------------------------------------------------------
The single-variable correlations showed repo age has the strongest effect
on stars_per_day -- but age is likely a confound, not an insight (older
repos mechanically show slower normalized growth). This script runs a
multiple regression so each feature's effect is estimated WHILE HOLDING
AGE CONSTANT, which tells you what actually matters independent of age.

SETUP:
  pip install statsmodels pandas
"""

import pandas as pd
import statsmodels.api as sm

df = pd.read_csv("analysis_summary.csv")

features = [
    "avg_weekly_commits",
    "avg_days_to_close",
    "description_length",
    "age_days",
]

model_df = df[features + ["stars_per_day"]].dropna()
print(f"Using {len(model_df)} repos with complete data for all features.\n")

X = model_df[features]
X = sm.add_constant(X)  # adds intercept term

# Log-transform the target: raw stars_per_day is heavily right-skewed
# (a handful of viral repos dominate), which violates OLS's normality
# assumption and shows up as huge skew/kurtosis in the diagnostics.
# log1p handles zeros safely.
import numpy as np
y = np.log1p(model_df["stars_per_day"])

model = sm.OLS(y, X).fit()
print(model.summary())

print("\n" + "=" * 60)
print("PLAIN-ENGLISH READ:")
print("=" * 60)
print("Look at the 'coef' and 'P>|t|' columns above for each feature.")
print("A feature with P>|t| < 0.05 has a real effect on growth EVEN")
print("AFTER controlling for repo age -- that's a much stronger claim")
print("than a raw correlation, because it rules out 'this only looked")
print("important because it's tangled up with how old the repo is.'")
