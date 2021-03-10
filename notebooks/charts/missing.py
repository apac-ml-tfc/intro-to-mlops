"""SMDW Chart Script: Summarize missing values by column"""

import altair as alt
import numpy as np
import pandas as pd

df_len = len(df)
colnames = df.columns.to_list()
# Something odd going on with list comprehensions throwing a NameError on `df` at the time of writing, so
# we'll just use a for loop:
nacounts = []
napcts = []
for c in colnames:
    nacount = df[c].isna().sum()
    nacounts.append(nacount)
    napcts.append(nacount / df_len)

chart_df = pd.DataFrame({
    "column": colnames,
    "nacount": nacounts,
    "napct": napcts,
})

bars = alt.Chart(
    chart_df,
    title=f"Missing values by field (from {df_len} records)",
).mark_bar().encode(
    x=alt.X("napct:Q", axis=alt.Axis(format='%'), title="Percentage of records"),
    y=alt.Y("column:N", sort=None, title="Field"),
)
text = bars.mark_text(
    align="left",
    baseline="middle",
    dx=3  # Nudges text to right so it doesn't appear on top of the bar
).encode(text="nacount:Q")

chart = bars + text
