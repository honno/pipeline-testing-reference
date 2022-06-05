from pathlib import Path

import pandas as pd
import pytest

from .v2_pipeline import best_preworkout_cereal_pipeline

mock_cereals = pd.read_csv(Path(__file__).parent / "v1_mock_cereals.csv")

mock_cereals_uppercase_cols = mock_cereals.copy()
mock_cereals_uppercase_cols.columns = mock_cereals.columns.str.upper()

mock_cereals_brand_col = mock_cereals.rename({"name": "brand"}, axis=1)


@pytest.mark.parametrize(
    "df", [mock_cereals, mock_cereals_uppercase_cols, mock_cereals_brand_col]
)
def test_smoke_pipeline(monkeypatch, df):
    monkeypatch.setattr(pd, "read_csv", lambda _: df)
    best_preworkout_cereal_pipeline.execute_in_process()
