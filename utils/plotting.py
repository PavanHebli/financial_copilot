import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Tuple
import utils.DataModels as dm
# from models import ChartMetadata  # assumes ChartMetadata is defined elsewhere


def normalize_chart_metadata(df: pd.DataFrame, metadata: dm.ChartMetadata) -> Tuple[pd.DataFrame, str, str]:
    """
    Normalize chart metadata to ensure x_column and y_column are populated.
    If missing, use groupby_column and aggregation to transform the dataframe.
    """
    x, y = metadata.x_column, metadata.y_column

    if not (x and y):
        groupby = metadata.groupby_column
        agg = metadata.aggregation or "count"

        if groupby and groupby in df.columns:
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            y_col = num_cols[0] if num_cols else df.columns[0]

            df = df.groupby(groupby).agg({y_col: agg}).reset_index()
            x = groupby
            y = df.columns[1]
        else:
            raise ValueError("Insufficient metadata to plot the chart.")

    if metadata.chart_type == "pie" and y not in df.columns and x in df.columns:
        df = df[x].value_counts().reset_index()
        df.columns = [x, "count"]
        y = "count"

    return df, x, y


def plot_chart(df: pd.DataFrame, metadata: dm.ChartMetadata):
    """
    Plot a chart based on normalized metadata.
    """
    if not metadata or not metadata.chart_type:
        return None

    df, x, y = normalize_chart_metadata(df, metadata)
    chart_type = metadata.chart_type

    fig, ax = plt.subplots()

    if chart_type == 'pie':
        data = df.set_index(x)[y]
        data.plot.pie(autopct='%1.1f%%', ax=ax)
        ax.set_ylabel('')
        ax.set_title(f"{y.replace('_', ' ').title()} by {x.replace('_', ' ').title()}")

    elif chart_type == 'bar':
        df.plot(x=x, y=y, kind='bar', ax=ax, legend=False)
        ax.set_xlabel(x.replace('_', ' ').title())
        ax.set_ylabel(y.replace('_', ' ').title())
        ax.set_title(f"{y.replace('_', ' ').title()} by {x.replace('_', ' ').title()}")
        ax.set_xticklabels(df[x], rotation=0)

    elif chart_type == 'line':
        df.plot(x=x, y=y, kind='line', ax=ax, legend=False)
        ax.set_xlabel(x.replace('_', ' ').title())
        ax.set_ylabel(y.replace('_', ' ').title())
        ax.set_title(f"{y.replace('_', ' ').title()} by {x.replace('_', ' ').title()}")

    elif chart_type == 'scatter':
        df.plot.scatter(x=x, y=y, ax=ax)
        ax.set_xlabel(x.replace('_', ' ').title())
        ax.set_ylabel(y.replace('_', ' ').title())
        ax.set_title(f"{y.replace('_', ' ').title()} vs {x.replace('_', ' ').title()}")

    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    plt.tight_layout()
    return fig
