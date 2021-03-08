"""SMDW Chart Script: Summarize missing values by column"""

import altair as alt
import numpy as np
import pandas as pd

colnames = df.columns.to_list()
nacounts = [df[c].isna().sum() for c in colnames]
df_len = len(df)

chart_df = pd.DataFrame({
    "column": colnames,
    "nacount": nacounts,
    "napct": [n / len(df) for n in nacounts],
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
