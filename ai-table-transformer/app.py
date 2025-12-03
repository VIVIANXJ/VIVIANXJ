import streamlit as st
import pandas as pd
import os

from core.table_loader import load_uploaded_tables
from core.join_key_detector import suggest_join_keys_for_pair
from core.merger import merge_tables_with_rules
from core.ai_mapping_engine import build_initial_mapping_df
from core.llm_transform import generate_transform_code_with_llm
from core.transformer_runner import apply_transform_code
from core.template_manager import (
    list_templates,
    save_template,
    load_template,
)
from utils.data_preview import df_to_sample_csv
from utils.logger import log


st.set_page_config(page_title="AI Table Merger & Transformer", layout="wide")
st.title("AI Table Merger & Transformer 🚀")
st.caption("Local deepseek-coder (via Ollama) + Streamlit | Multi-table merge & flexible format transform")

# ---------- Session State ----------
if "tables" not in st.session_state:
    st.session_state.tables = {}  # name -> DataFrame
if "join_rules" not in st.session_state:
    st.session_state.join_rules = []  # list of dict
if "merged_df" not in st.session_state:
    st.session_state.merged_df = None
if "mapping_df" not in st.session_state:
    st.session_state.mapping_df = None
if "transform_code" not in st.session_state:
    st.session_state.transform_code = ""
if "template_loaded" not in st.session_state:
    st.session_state.template_loaded = None
if "skip_merge" not in st.session_state:
    st.session_state.skip_merge = False
if "d_sample_df" not in st.session_state:
    st.session_state.d_sample_df = None


# ---------- Step 0: Template load / save ----------
st.sidebar.header("Templates")

with st.sidebar.expander("Load Template", expanded=True):
    templates = list_templates()
    if templates:
        tpl_name = st.selectbox("Available templates", ["<None>"] + templates)
        if tpl_name != "<None>":
            if st.button("Load Selected Template"):
                (
                    join_rules,
                    mapping_df,
                    transform_code,
                    metadata,
                ) = load_template(tpl_name)
                st.session_state.join_rules = join_rules
                st.session_state.mapping_df = mapping_df
                st.session_state.transform_code = transform_code
                st.session_state.template_loaded = tpl_name
                st.success(f"Template '{tpl_name}' loaded (join rules & mapping & code).")
    else:
        st.caption("No templates yet. Save one after you finish configuration.")

with st.sidebar.expander("Save Template"):
    tpl_save_name = st.text_input("Template name (folder name under /templates)")
    if st.button("Save current configuration as template"):
        if not tpl_save_name.strip():
            st.error("Please enter a template name.")
        elif st.session_state.merged_df is None:
            st.error("Please create a merged table before saving a template.")
        elif st.session_state.mapping_df is None or st.session_state.mapping_df.empty:
            st.error("Please configure column mapping before saving a template.")
        elif not st.session_state.transform_code.strip():
            st.error("Please generate transform code before saving a template.")
        else:
            save_template(
                tpl_save_name.strip(),
                join_rules=st.session_state.join_rules,
                mapping_df=st.session_state.mapping_df,
                transform_code=st.session_state.transform_code,
                metadata={"note": "Auto-saved by AI Table Merger & Transformer"},
            )
            st.success(f"Template '{tpl_save_name.strip()}' saved.")


st.markdown("---")

# ---------- Step 1: Upload tables ----------
st.header("Step 1: Upload Source Tables (Multiple)")

uploaded_files = st.file_uploader(
    "Upload one or more CSV / Excel files (orders, customers, sku list, etc.)",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
)

if uploaded_files:
    tables = load_uploaded_tables(uploaded_files)
    st.session_state.tables = tables

if not st.session_state.tables:
    st.info("Please upload at least one table to continue.")
    st.stop()

st.subheader("Preview Uploaded Tables")
for name, df in st.session_state.tables.items():
    st.markdown(f"**Table: {name}** — Columns: {list(df.columns)}")
    st.dataframe(df.head())

table_names = list(st.session_state.tables.keys())

st.markdown("---")

# ⭐ Allow user to pick one of the uploaded tables as the merged base table
st.subheader("Optional: Use one of the uploaded tables as the merged base table")

use_uploaded_as_merged = st.checkbox(
    "Use one of the uploaded source tables directly as the merged table (skip Step 2 join)",
    value=False
)

if use_uploaded_as_merged:
    selected_merged_table = st.selectbox(
        "Select the table to use as merged table",
        table_names,
        key="select_direct_merged"
    )

    if selected_merged_table:
        st.session_state.merged_df = st.session_state.tables[selected_merged_table]
        st.session_state.skip_merge = True   # auto-skip Step 2
        st.success(f"Using '{selected_merged_table}' as the merged base table.")
        st.subheader("Merged Table Preview")
        st.dataframe(st.session_state.merged_df.head())

# ⭐ 新增：允许跳过 Step 2，直接上传已经合并好的总表
st.subheader("Optional: Use an already merged table")

skip_merge_checkbox = st.checkbox(
    "I already have a fully merged table and want to skip joining in Step 2",
    value=st.session_state.skip_merge,
)
st.session_state.skip_merge = skip_merge_checkbox

if skip_merge_checkbox:
    merged_direct_file = st.file_uploader(
        "Upload your merged table (CSV / Excel)",
        type=["csv", "xlsx", "xls"],
        key="merged_direct_file",
    )
    if merged_direct_file is not None:
        if merged_direct_file.name.endswith((".xlsx", ".xls")):
            merged_direct_df = pd.read_excel(merged_direct_file)
        else:
            merged_direct_df = pd.read_csv(merged_direct_file)

        st.session_state.merged_df = merged_direct_df
        st.success("Merged table uploaded and will be used as the base table.")
        st.subheader("Uploaded Merged Table Preview")
        st.dataframe(merged_direct_df.head())


# ---------- Step 2: Configure join rules (manual but with suggestions) ----------
if not st.session_state.skip_merge:
    st.header("Step 2: Configure Join Rules (Manual, with Suggestions)")

    st.caption(
        "You can define how tables are joined. This tool does NOT auto-chain joins; "
        "you control each join rule for maximum reliability."
    )

    # join_rules: list of dicts: {left_table, right_table, left_key, right_key, how}
    if "join_rules" not in st.session_state or st.session_state.join_rules is None:
        st.session_state.join_rules = []

    # UI to add/edit join rules
    new_join_expander = st.expander("Add / Edit Join Rules", expanded=True)

    with new_join_expander:
        st.write("Each join rule merges a RIGHT table into a LEFT table on specific key columns.")

        # Show current join rules
        if st.session_state.join_rules:
            st.markdown("**Current Join Rules:**")
            for idx, jr in enumerate(st.session_state.join_rules):
                st.write(
                    f"{idx+1}. {jr['left_table']}.{jr['left_key']} "
                    f"{jr.get('how','left').upper()} JOIN "
                    f"{jr['right_table']}.{jr['right_key']}"
                )
        else:
            st.caption("No join rules yet.")

        st.markdown("**Create / Update a Join Rule**")
        col1, col2, col3 = st.columns(3)
        with col1:
            left_table_sel = st.selectbox("Left table", table_names, key="jr_left_table")
        with col2:
            right_table_sel = st.selectbox(
                "Right table", [t for t in table_names if t != left_table_sel], key="jr_right_table"
            )
        with col3:
            how_sel = st.selectbox("Join type", ["left", "inner", "right", "outer"], index=0, key="jr_how")

        # suggest join keys
        left_df = st.session_state.tables[left_table_sel]
        right_df = st.session_state.tables[right_table_sel]

        suggestions = suggest_join_keys_for_pair(left_df, left_table_sel, right_df, right_table_sel)
        suggestion_text = (
            ", ".join(
                [
                    f"{s['left_col']} ↔ {s['right_col']} (score={s['score']:.2f})"
                    for s in suggestions[:3]
                ]
            )
            if suggestions
            else "No strong suggestion. Please choose manually."
        )
        st.caption(f"Auto join key suggestions (top 3): {suggestion_text}")

        left_key = st.selectbox("Left key column", list(left_df.columns), key="jr_left_key")
        right_key = st.selectbox("Right key column", list(right_df.columns), key="jr_right_key")

        add_or_update = st.radio("Action", ["Add new", "Replace all"], horizontal=True)

        if st.button("Apply Join Rule"):
            new_rule = {
                "left_table": left_table_sel,
                "right_table": right_table_sel,
                "left_key": left_key,
                "right_key": right_key,
                "how": how_sel,
            }
            if add_or_update == "Replace all":
                st.session_state.join_rules = [new_rule]
            else:
                st.session_state.join_rules.append(new_rule)
            st.success("Join rule updated.")

        if st.button("Clear All Join Rules"):
            st.session_state.join_rules = []
            st.success("All join rules cleared.")

    # Perform merge preview
    if st.button("Merge Tables with Current Join Rules"):
        if not st.session_state.join_rules:
            st.error("No join rules defined. Please define at least one.")
        else:
            merged_df = merge_tables_with_rules(st.session_state.tables, st.session_state.join_rules)
            if merged_df is None:
                st.error("Merge failed. Please check join rules.")
            else:
                st.session_state.merged_df = merged_df
                st.success("Tables merged successfully.")
                st.subheader("Merged Table Preview")
                st.dataframe(merged_df.head())
else:
    # ⭐ 如果用户选择 skip merge，就在 Step 2 显示一个提示，而不再强制配置 join
    st.header("Step 2: Merge Tables (Skipped)")
    st.caption("You chose to use an already merged table in Step 1, so this step is skipped.")


# ---------- Step 3: Configure mapping (AI Guess + manual override) ----------
st.header("Step 3: Configure Target Table D Mapping")

st.caption(
    "Upload a small sample of your desired final table D, then let the tool auto-guess mapping. "
    "You can manually adjust the mapping for full control."
)

d_sample_file = st.file_uploader(
    "Upload sample of target table D (CSV/Excel, only a few rows needed)",
    type=["csv", "xlsx", "xls"],
    key="d_sample",
)

if d_sample_file:
    if d_sample_file.name.endswith((".xlsx", ".xls")):
        d_sample_df = pd.read_excel(d_sample_file)
    else:
        d_sample_df = pd.read_csv(d_sample_file)

    st.session_state.d_sample_df = d_sample_df

    st.subheader("Target Table D Sample Preview")
    st.dataframe(d_sample_df.head())

    if st.button("Auto-Guess Mapping (no LLM, heuristic)"):
        merged_df = st.session_state.merged_df
        mapping_df = build_initial_mapping_df(merged_df, d_sample_df)
        st.session_state.mapping_df = mapping_df
        st.success("Initial mapping guessed. You can adjust it below.")

# ---- guard: ensure mapping_df is ready ----
mapping_df_state = st.session_state.get("mapping_df", None)

if mapping_df_state is None or not isinstance(mapping_df_state, pd.DataFrame) or mapping_df_state.empty:
    st.info("Please upload a D sample and click 'Auto-Guess Mapping' (or load a template) before editing the mapping.")
    st.stop()


st.subheader("Common Expression Templates")

common_expr = {
    "Split by space (first part)": 'row["{col}"].split(" ")[0]',
    "Split by space (second part)": 'row["{col}"].split(" ")[1]',
    "Split by space (third part)": 'row["{col}"].split(" ")[2]',
    "Split by comma (first part)": 'row["{col}"].split(",")[0]',
    "Split by comma (second part)": 'row["{col}"].split(",")[1]',
    "Split by comma (third part)": 'row["{col}"].split(",")[2]',
    "Strip whitespace": 'row["{col}"].strip()',
    "Get first item of any delimiter": 'row["{col}"].split(delimiter)[0]',
    "Get last item of any delimiter": 'row["{col}"].split(delimiter)[-1]',
}

selected_expr = st.selectbox(
    "Choose an expression template to insert",
    ["(Select a template)"] + list(common_expr.keys())
)

if selected_expr != "(Select a template)":
    st.info(
        f"Selected template:\n\n```\n{common_expr[selected_expr]}\n```"
        "\nReplace `{col}` with the source column."
    )


st.subheader("Edit Column Mapping")
st.caption(
    "For each target column, choose a source column from merged table or leave empty and/or add an expression."
)

merged_columns = list(st.session_state.merged_df.columns)
mapping_df = mapping_df_state.copy()


editable_rows = []
for idx, row in mapping_df.iterrows():
    st.markdown(f"**Target column: `{row['target_column']}`**")
    c1, c2 = st.columns([2, 3])
    with c1:
        source_choice = st.selectbox(
            "Source column (optional)",
            ["<None>"] + merged_columns,
            index=(merged_columns.index(row["source_column"]) + 1) if row["source_column"] in merged_columns else 0,
            key=f"map_source_{idx}",
        )
    with c2:
        expr = st.text_input(
            "Custom expression (optional, Python using row[...] )",
            value=row.get("expression", "") or "",
            key=f"map_expr_{idx}",
        )
    editable_rows.append(
        {
            "target_column": row["target_column"],
            "source_column": None if source_choice == "<None>" else source_choice,
            "expression": expr.strip() or None,
        }
    )

mapping_df = pd.DataFrame(editable_rows)
st.session_state.mapping_df = mapping_df

st.markdown("Preview of mapping:")
st.dataframe(mapping_df)

st.markdown("---")

# ---------- Step 4: Generate transform(row) code via deepseek-coder ----------
st.header("Step 4: Generate transform(row) Code via Local deepseek-coder (Ollama)")

if st.button("Generate transform(row) with DeepSeek (based on mapping & samples)"):
    merged_sample_csv = df_to_sample_csv(st.session_state.merged_df, n_rows=10)

    # ⭐ 优先使用在 Step 3 已经读好的 d_sample_df
    d_sample_df_state = st.session_state.get("d_sample_df", None)

    if d_sample_df_state is None or not isinstance(d_sample_df_state, pd.DataFrame) or d_sample_df_state.empty:
        # 如果没有有效的 D sample，就根据 mapping 的 target 列名造一个只带表头的空 df
        d_sample_df = pd.DataFrame(columns=mapping_df["target_column"].tolist())
    else:
        d_sample_df = d_sample_df_state

    d_sample_csv = df_to_sample_csv(d_sample_df, n_rows=10)

    try:
        with st.spinner("Calling local deepseek-coder via Ollama to generate transform(row)..."):
            code = generate_transform_code_with_llm(
                merged_sample_csv=merged_sample_csv,
                target_sample_csv=d_sample_csv,
                mapping_df=mapping_df,
            )
        st.session_state.transform_code = code
        st.success("Transform code generated.")
    except Exception as e:
        st.error(f"Failed to generate transform code: {e}")


if not st.session_state.transform_code:
    st.info("Transform code not generated yet. Click the button above to generate.")
else:
    st.subheader("Transform Code (editable)")
    edited_code = st.text_area(
        "Edit transform(row) Python code if needed",
        value=st.session_state.transform_code,
        height=350,
    )
    st.session_state.transform_code = edited_code

st.markdown("---")

# ---------- Step 5: Run transform & download result ----------
st.header("Step 5: Run transform(row) & Download Final Table D")

if st.button("Run transform(row) on merged table"):
    try:
        df_result, error = apply_transform_code(
            st.session_state.transform_code,
            st.session_state.merged_df,
        )
        if error:
            st.error(f"Error while applying transform: {error}")
        else:
            st.success("Transform applied successfully.")
            st.subheader("Result Preview (final table D)")
            st.dataframe(df_result.head())
            st.download_button(
                "Download Table D as CSV",
                data=df_result.to_csv(index=False),
                file_name="table_D.csv",
                mime="text/csv",
            )
    except Exception as e:
        st.error(f"Unexpected error: {e}")





