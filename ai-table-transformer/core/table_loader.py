import os
import pandas as pd


def load_uploaded_tables(uploaded_files):
    """
    Turn a list of uploaded files into a dict: {table_name: DataFrame}.
    Table name is derived from file name without extension.
    """
    tables = {}
    for f in uploaded_files:
        name = os.path.splitext(f.name)[0]
        if f.name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(f)
        else:
            df = pd.read_csv(f)
        tables[name] = df
    return tables
