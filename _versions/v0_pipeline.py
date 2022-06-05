import pandas as pd
from dagster import get_dagster_logger, job, op


@op
def download_latest_cereals() -> pd.DataFrame:
    df = pd.read_csv("https://docs.dagster.io/assets/cereal.csv")
    return df


@op
def find_highest_protein_cereal(df: pd.DataFrame) -> str:
    sorted_df = df.sort_values("protein", ascending=False)
    return sorted_df.iloc[0]["name"]


@op
def display_highest_protein_cereal(name: str):
    logger = get_dagster_logger()
    logger.info(f"Most protein-rich cereal: {name}")


@job
def best_preworkout_cereal_pipeline():
    df = download_latest_cereals()
    name = find_highest_protein_cereal(df)
    display_highest_protein_cereal(name)
