from utils.similarity import name_similarity
from core.type_detector import detect_column_type
import pandas as pd


def suggest_join_keys_for_pair(
    df_left: pd.DataFrame,
    left_name: str,
    df_right: pd.DataFrame,
    right_name: str,
    max_suggestions: int = 5,
):
    """
    Suggest possible join key pairs between df_left and df_right,
    based on column name similarity + heuristic type similarity + value overlap.
    Returns a list of dicts: {left_col, right_col, score}.
    """
    suggestions = []

    for lc in df_left.columns:
        left_type = detect_column_type(df_left[lc], lc)
        left_values = set(df_left[lc].dropna().astype(str).head(200))

        for rc in df_right.columns:
            right_type = detect_column_type(df_right[rc], rc)
            right_values = set(df_right[rc].dropna().astype(str).head(200))

            # type compatibility
            type_score = 1.0 if left_type == right_type else 0.6

            # name similarity
            ns = name_similarity(lc, rc)

            # value overlap
            if left_values and right_values:
                inter = left_values & right_values
                overlap_ratio = len(inter) / max(len(left_values), 1)
            else:
                overlap_ratio = 0.0

            score = 0.5 * ns + 0.2 * type_score + 0.3 * overlap_ratio
            if score > 0.3:  # threshold
                suggestions.append(
                    {
                        "left_col": lc,
                        "right_col": rc,
                        "score": score,
                    }
                )

    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions[:max_suggestions]

