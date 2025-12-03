import pandas as pd
from core.type_detector import detect_column_type
from utils.similarity import name_similarity


def build_initial_mapping_df(merged_df: pd.DataFrame, d_sample_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build an initial mapping DataFrame with heuristic "AI-like" guesses:
    columns: target_column, source_column, expression
    """
    target_cols = list(d_sample_df.columns)
    merged_cols = list(merged_df.columns)

    rows = []

    # Precompute column types for merged table
    merged_types = {
        col: detect_column_type(merged_df[col], col) for col in merged_cols
    }

    for tcol in target_cols:
        # try to guess best matching merged column
        best_col = None
        best_score = 0.0
        t_type = None  # no strong type for target, we only use name similarity + type hint

        for mcol in merged_cols:
            ns = name_similarity(tcol, mcol)
            m_type = merged_types[mcol]

            # Give small bonus for compatible type (very rough)
            type_bonus = 0.1 if (("id" in tcol.lower() and m_type == "id") or (m_type != "id")) else 0.0
            score = ns + type_bonus

            if score > best_score:
                best_score = score
                best_col = mcol

        rows.append(
            {
                "target_column": tcol,
                "source_column": best_col if best_score >= 0.3 else None,
                "expression": None,
            }
        )

    return pd.DataFrame(rows)
