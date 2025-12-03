import pandas as pd
from typing import Tuple, Optional


def apply_transform_code(
    code: str,
    merged_df: pd.DataFrame,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Execute given Python code to obtain transform(row), then apply it to merged_df.
    Returns (result_df, error_message).
    WARNING: This uses exec() and is intended for local/internal use only.
    """
    local_vars = {}
    try:
        exec(code, {}, local_vars)
    except Exception as e:
        return None, f"Error executing code: {e}"

    transform = local_vars.get("transform")
    if not callable(transform):
        return None, "transform(row) function not found in code."

    out_rows = []
    for _, row in merged_df.iterrows():
        try:
            out = transform(row)
        except Exception as e:
            return None, f"Error applying transform to a row: {e}"
        out_rows.append(out)

    try:
        result_df = pd.DataFrame(out_rows)
    except Exception as e:
        return None, f"Error building result DataFrame: {e}"

    return result_df, None
