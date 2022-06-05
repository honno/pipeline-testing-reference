from pathlib import Path

import pandas as pd
import pytest

from pipeline import best_preworkout_cereal_pipeline, find_highest_protein_cereal

mock_cereals = pd.read_csv(Path(__file__).parent / "mock_cereals.csv")
assert isinstance(mock_cereals, pd.DataFrame)  # for mypy

mock_cereals_uppercase_cols = mock_cereals.copy()
mock_cereals_uppercase_cols.columns = mock_cereals.columns.str.upper()

mock_cereals_brand_col = mock_cereals.rename({"name": "brand"}, axis=1)


@pytest.mark.parametrize(
    "df", [mock_cereals, mock_cereals_uppercase_cols, mock_cereals_brand_col]
)
def test_smoke_pipeline(monkeypatch, df):
    monkeypatch.setattr(pd, "read_csv", lambda _: df)
    best_preworkout_cereal_pipeline.execute_in_process()


def test_find_highest_protein_cereal():
    df = pd.DataFrame(
        {
            "name": ["Bran", "Bran - no added sugars", "Honey-comb"],
            "protein": [4, 4, 1],
            "calories": [70, 50, 110],
        }
    )
    assert "Bran - no added sugars" == find_highest_protein_cereal(df)
