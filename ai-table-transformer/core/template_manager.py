import os
import json
import pandas as pd
from typing import List, Tuple


TEMPLATE_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _ensure_template_root():
    os.makedirs(TEMPLATE_ROOT, exist_ok=True)


def list_templates() -> List[str]:
    _ensure_template_root()
    names = []
    for entry in os.listdir(TEMPLATE_ROOT):
        path = os.path.join(TEMPLATE_ROOT, entry)
        if os.path.isdir(path):
            names.append(entry)
    return sorted(names)


def save_template(
    name: str,
    join_rules: List[dict],
    mapping_df: pd.DataFrame,
    transform_code: str,
    metadata: dict | None = None,
):
    _ensure_template_root()
    tpl_dir = os.path.join(TEMPLATE_ROOT, name)
    os.makedirs(tpl_dir, exist_ok=True)

    # save join_rules.csv
    jr_df = pd.DataFrame(join_rules)
    jr_df.to_csv(os.path.join(tpl_dir, "join_rules.csv"), index=False)

    # save column_mapping.csv
    mapping_df.to_csv(os.path.join(tpl_dir, "column_mapping.csv"), index=False)

    # save transform_code.py
    with open(os.path.join(tpl_dir, "transform_code.py"), "w", encoding="utf-8") as f:
        f.write(transform_code)

    # save metadata.json
    meta = metadata or {}
    meta["template_name"] = name
    with open(os.path.join(tpl_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_template(
    name: str,
) -> Tuple[List[dict], pd.DataFrame, str, dict]:
    _ensure_template_root()
    tpl_dir = os.path.join(TEMPLATE_ROOT, name)
    if not os.path.isdir(tpl_dir):
        raise FileNotFoundError(f"Template '{name}' not found.")

    # join_rules
    jr_path = os.path.join(tpl_dir, "join_rules.csv")
    jr_df = pd.read_csv(jr_path)
    join_rules = jr_df.to_dict(orient="records")

    # column_mapping
    mapping_path = os.path.join(tpl_dir, "column_mapping.csv")
    mapping_df = pd.read_csv(mapping_path)

    # transform code
    code_path = os.path.join(tpl_dir, "transform_code.py")
    with open(code_path, "r", encoding="utf-8") as f:
        transform_code = f.read()

    # metadata
    meta_path = os.path.join(tpl_dir, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    else:
        metadata = {}

    return join_rules, mapping_df, transform_code, metadata
