import pandas as pd
from io import StringIO


def df_to_sample_csv(df: pd.DataFrame, n_rows: int = 10) -> str:
    """
    Convert first n_rows of df into CSV text (no index),
    suitable for feeding into LLM context.
    """
    return df.head(n_rows).to_csv(index=False)
