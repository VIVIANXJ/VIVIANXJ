import subprocess
import textwrap
import pandas as pd
from utils.data_preview import df_to_sample_csv


def _clean_llm_code(raw: str) -> str:
    content = raw.strip()
    if "```" not in content:
        return content
    parts = content.split("```")
    for part in parts:
        if "def transform" in part or "import " in part:
            return part.strip()
    return content


def generate_transform_code_with_llm(
    merged_sample_csv: str,
    target_sample_csv: str,
    mapping_df: pd.DataFrame,
    model_name: str = "deepseek-coder:1.3b",
) -> str:
    """
    Use local deepseek-coder via Ollama to generate Python transform(row) code.
    mapping_df has columns: target_column, source_column, expression.
    """
    mapping_text_lines = []
    for _, row in mapping_df.iterrows():
        mapping_text_lines.append(
            f"- {row['target_column']} <= "
            f"{row['source_column'] or 'None'} ; expr={row['expression'] or 'None'}"
        )
    mapping_text = "\n".join(mapping_text_lines)

    system_prompt = (
        "You are an expert Python data engineer. "
        "You will generate a Python function transform(row) that converts a row of "
        "the merged table into a row of the final target table D."
    )

    user_prompt = f"""
Here is a CSV sample of the merged source table:

[MERGED SOURCE SAMPLE CSV]
{merged_sample_csv}

Here is a CSV sample of the target table D:

[TARGET D SAMPLE CSV]
{target_sample_csv}

Below are user-provided mapping hints between columns:

[MAPPING HINTS]
{mapping_text}

- For each target column, if source_column is not None, use that as primary data source.
- If an expression is provided (expr=...), you may implement that using the 'row' (pandas Series).
- You may also add simple type conversions, date formatting (using pandas.to_datetime), and numeric calculations.

Now write Python code that:

- Imports pandas as pd.
- Defines a function: def transform(row):
- 'row' is a pandas Series with all merged columns available by name.
- The function returns a dict where:
    * Keys are exactly the target table D column names.
    * Values are computed from 'row' according to the mapping hints and the target sample.
- Do not read or write any files.
- Do not print anything.
- Output ONLY complete Python code, including imports and the transform function.
"""

    prompt = f"{system_prompt}\n\n{user_prompt}"

    result = subprocess.run(
        ["ollama", "run", model_name],
        input=prompt,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Ollama/deepseek-coder failed: {result.stderr}")

    raw_output = result.stdout
    code = _clean_llm_code(raw_output)
    return textwrap.dedent(code).strip()
