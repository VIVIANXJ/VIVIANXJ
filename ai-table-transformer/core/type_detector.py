import pandas as pd
import re


def detect_column_type(series: pd.Series, col_name: str) -> str:
    """
    Very simple heuristic type detector for columns.
    Returns one of: 'id', 'date', 'amount', 'name', 'text', 'unknown'
    """
    name_lower = col_name.lower()

    # name-based hints
    if any(k in name_lower for k in ["id", "code", "no", "number"]):
        return "id"
    if "date" in name_lower or "time" in name_lower:
        return "date"
    if any(k in name_lower for k in ["price", "amount", "total", "cost"]):
        return "amount"
    if any(k in name_lower for k in ["name", "customer", "client", "person"]):
        return "name"

    # value-based hints
    sample = series.dropna().astype(str).head(20)

    # check numeric
    numeric_count = 0
    money_like = 0
    date_like = 0
    for v in sample:
        if re.fullmatch(r"-?\d+(\.\d+)?", v):
            numeric_count += 1
        if re.search(r"\$", v):
            money_like += 1
        if re.search(r"\d{4}-\d{1,2}-\d{1,2}", v) or re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", v):
            date_like += 1

    if date_like >= len(sample) * 0.5:
        return "date"
    if money_like >= len(sample) * 0.3 or numeric_count >= len(sample) * 0.8:
        return "amount"

    # fallback
    return "text"
