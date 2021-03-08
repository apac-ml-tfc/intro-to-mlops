"""SMDW Chart Script: Plot top and tail unique values for all str columns in df"""

import altair as alt
import numpy as np
import pandas as pd

# Configuration:
half_lim_values = 3

charts = []
df_len = len(df)
for col in df:
    if not pd.api.types.is_numeric_dtype(df[col].dtype):
        continue

    chart_df = df[[col]].copy()
    chart_df["Field"] = col
    col_chart = alt.Chart(chart_df).transform_density(
        col,
        as_=[col, "density"],
        extent=[df[col].min(), df[col].max()],
        groupby=["Field"],
    ).mark_area(orient='horizontal').encode(
        y=f"{col}:Q",
        #color='Origin:N',
        x=alt.X(
            "density:Q",
            stack='center',
            impute=None,
            title=None,
            axis=alt.Axis(labels=False, values=[0],grid=False, ticks=True),
        ),
        column=alt.Column(
            "Field:N",
#             header=alt.Header(
#                 titleOrient='bottom',
#                 labelOrient='bottom',
#                 labelPadding=0,
#             ),
        )
    ).properties(
        width=100
    )
#     .configure_facet(
#         spacing=0
#     ).configure_view(
#         stroke=None
#     )
    charts.append(col_chart)

# chart = charts[0]
chart = alt.hconcat(
    *charts,
    title=f"Numeric field distributions (from {df_len} total records)",
).configure_facet(
    spacing=0
).configure_view(
    stroke=None
)
