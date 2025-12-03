import pandas as pd
from typing import Dict, List


def merge_tables_with_rules(
    tables: Dict[str, pd.DataFrame],
    join_rules: List[dict],
) -> pd.DataFrame | None:
    """
    Sequentially apply join rules.
    join_rules: list of dict with keys:
      left_table, right_table, left_key, right_key, how
    We always start from the first rule's left_table as base,
    then apply each rule's join in listed order.
    """
    if not join_rules:
        return None

    first_left = join_rules[0]["left_table"]
    if first_left not in tables:
        return None

    merged = tables[first_left].copy()

    for jr in join_rules:
        lt = jr["left_table"]
        rt = jr["right_table"]
        lk = jr["left_key"]
        rk = jr["right_key"]
        how = jr.get("how", "left")

        if rt not in tables:
            continue

        right_df = tables[rt]

        # If current merged doesn't have the left key yet (e.g. user changed base),
        # we still attempt merge on the named column.
        if lk not in merged.columns:
            # user might have misconfigured; we skip this rule
            continue

        merged = merged.merge(
            right_df,
            left_on=lk,
            right_on=rk,
            how=how,
            suffixes=("", f"_{rt}"),
        )

    return merged
