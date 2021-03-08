"""SMDW Chart Script: Plot top and tail unique values for all str columns in df"""

import altair as alt
import numpy as np
import pandas as pd

# Configuration:
half_lim_values = 3

charts = []
df_len = len(df)
for col in df:
    if pd.api.types.is_string_dtype(df[col].dtype):
        uniques = df[col].value_counts()
        n_uniques = len(uniques)
        if n_uniques <= (half_lim_values * 2):
            chart_df = pd.DataFrame({
                "value": uniques.index.to_list(),
                "count": uniques,
                "pct": uniques / df_len,
            })
        else:
            head_sr = uniques.head(half_lim_values)
            tail_sr = uniques.tail(half_lim_values)
            remainder = uniques[half_lim_values:-half_lim_values]
            counts = np.concatenate((head_sr, [remainder.sum()], tail_sr))
#                 counts = pd.concat((head_sr, [remainder.sum()], tail_sr))
            chart_df = pd.DataFrame({
                "value": head_sr.index.to_list() + ["..[Others].."] + tail_sr.index.to_list(),
                "count": counts,
                "pct": counts / df_len,
            })
#         display(chart_df.head())
        bars = alt.Chart(chart_df, title=f"Field: {col}").mark_bar().encode(
            x=alt.X("pct:Q", axis=alt.Axis(format='%'), title="Percentage of records"),
            y=alt.Y("value:N", sort=None, title="Value"),
        )
        text = bars.mark_text(
            align="left",
            baseline="middle",
            dx=3  # Nudges text to right so it doesn't appear on top of the bar
        ).encode(text="count:Q")
        charts.append(bars + text)

chart = alt.vconcat(
    *charts,
    title=f"Most- and least-common values per categorical field (from {df_len} total records)",
)
