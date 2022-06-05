from pathlib import Path

import pandas as pd

from .v0_pipeline import best_preworkout_cereal_pipeline

mock_cereals = pd.read_csv(Path(__file__).parent / "v1_mock_cereals.csv")


def test_smoke_pipeline(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **kw: mock_cereals)
    best_preworkout_cereal_pipeline.execute_in_process()
