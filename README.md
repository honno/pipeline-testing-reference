# Pipeline testing reference

Here we'll go through a basic pipeline and the where/how/when to test it.

TODO:

* appropriate headings and section breaks
* quick intro
* note blocks
* quick mypy talk

## 0

For this scenario we've been tasked to automate the process of recommending the best cereal to have when body building. We'll want to build a pipeline, and decide on using Dagster for data orchestration. We'll use pandas for loading/manipulating/analysing the data.
We decide to start out simple and build our pipeline just to recommend a cereal by **finding the highest protein (grams per serving) cereal** in the latest cereal dataset.

The cereal data consists of the attributes "name", "protein" and "calories", as well as other columns containing additional information, e.g.

|            name | protein | calories | ...   |
| --------------- | ------- | -------- | ----- |
|  Apple Cheerios |       2 |      110 |       |
|     Apple Jacks |       2 |      110 |       |
|         Basic 4 |       3 |      130 |       |
|             ... |         |          |       |

We explore the data a bit and come up with an initial prototype.

```python
# pipeline.py
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
```

> :grey_question: Note
> 
> I wouldn't worry about writing tests until you have a sense of what the API should look like.

Our pipeline `best_preworkout_cereal_pipeline()` uses:

1. `download_latest_cereals()` to retrieve the latest cereals data, and converts it to a [`pandas.DataFrame`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html). Note [`pd.read_csv(<url>)`](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html) does this all at once.
2. `find_highest_protein_cereal()` to sort the cereals data via the "protein" column (in descending order), and get the name of first row, i.e. the cereal containing the most protein.
3. `display_highest_protein_cereal()` to log the cereal containing the most protein.

To see if our pipeline actually works,

```python
$ dagster job execute -f pipeline.py
INFO - Most protein-rich cereal: Cheerios
```

## 1

We have a working pipeline! Now is the best time to ensure it keeps on working by writing a smoke test, i.e. a very simple test that sees if our given program runs without failures.

```python
# test_pipeline.py
from pipeline import best_preworkout_cereal_pipeline


def test_smoke_pipeline():
    best_preworkout_cereal_pipeline.execute_in_process()
```

This can be run via `pytest`,

```python
$ pytest test_pipeline.py -v
===================== test session starts ======================
test_pipeline.py::test_smoke_pipeline PASSED
```

Running tests locally is very useful whilst developing, but it's also a good idea to ensure they run when we push changes to GitHub, namely so pull request authors will see when they've pushed a breaking change even if they didn't test locally. A simple config for the GitHub Actions CI could lool like,

```yaml
# .github/workflows/test.yml
name: Run tests
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout pipeline
      uses: actions/checkout@main
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.8
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: |
        pytest test_pipeline.py
```

Let's assume in our scenario that we're not using the free and public `"https://docs.dagster.io/assets/cereal.csv"` endpoint for the latest cereals data, but a large and private endpoint. A major limitation to our smoke test is that it would be impractical to pull such a dataset when testing:

* Using a live web endpoint means any downtime prevents testing
* Large datasets might take a long time to both download and parse
* Private endpoints should require authentication, which is impractical when running tests both locally and on CI
* Any sensitive data could be leaked on CI logs

So we should create a minimal dataset that just looks like the kind of data we expect (e.g. [mock_cereals.csv](./mock_cereals.csv)), and then make the pipeline use that when testing. We can use the the handy [`monkeypatch`](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) fixture to inject this mocked data into our pipeline.

> :grey_question: Note
> 
> fixtures TODO	

```python
# test_pipeline.py
from pathlib import Path

import pandas as pd

from pipeline import best_preworkout_cereal_pipeline

mock_cereals = pd.read_csv(Path(__file__).parent / "mock_cereals.csv")


def test_smoke_pipeline(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda _: mock_cereals)
    best_preworkout_cereal_pipeline.execute_in_process()
```

Monkey-patching a third-party function like `pd.read_csv()` is not ideal, as we (or another third-party library) might need to use it elsewhere in the future. However in this use case, other solutions for injecting our mocked dataset are more complicated and thus time-consuming to implement/maintain (e.g. [Dagster resources](https://docs.dagster.io/tutorial/advanced-tutorial/resources)), so it's quite valid to go with the easier solution that Just Works™ for now—rarely should testing be a chore!

## 2

Let's say you run the pipeline the next day and it halts due to an error,

```python
$ dagster job execute -f pipeline.py
KeyError: 'protein'
```

Upon investigation, you see that the latest cereal dataset has had its column names capitalized. We'll want to accommodate such datasets. Before we work on updating the pipeline however, we'd do well to write a respective test first. Writing the test beforehand is useful as:

* You can see your test fail, which reassures your test is working as intended.
* You reflect on what you're actually trying to fix (e.g. we want to the pipeline to run without errors when column names are not all lower-cased), which typically leads to higher-quality code changes.

```python
# test_pipeline.py
mock_cereals_uppercase_cols = mock_cereals.copy()
mock_cereals_uppercase_cols.columns = mock_cereals.columns.str.upper()


def test_smoke_pipeline_uppercase_cols(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda _: mock_cereals_uppercase_cols)
    best_preworkout_cereal_pipeline.execute_in_process()
```

We don't assert anything here as we just want to see our pipeline runs without errors. As we intended, running this test it fails with the same failure we got before,

```python
$ pytest test_pipeline.py::test_smoke_pipeline_uppercase_cols -v
===================== test session starts ======================
test_pipeline.py::test_smoke_pipeline_uppercase_cols FAILED
...
KeyError: 'protein'
```

Now we have our failing test, we work on our solution. We opt to sanitise column names, creating a new op `preprocess_cereals()` to encapsulate such pre-processing needs.

```python
# pipeline.py
@op
def preprocess_cereals(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.lower()
    return df

...

@job
def best_preworkout_cereal_pipeline():
    df = download_latest_cereals()
    df = preprocess_cereals(df)
    name = find_highest_protein_cereal(df)
    display_highest_protein_cereal(name)
``` 

Whenever we think we might have resolved the problem, we run the corresponding test, e.g.

```python
$ pytest test_pipeline.py::test_smoke_pipeline_uppercase_cols -v
===================== test session starts ======================
test_pipeline.py::test_smoke_pipeline_uppercase_cols PASSED
```

It passes! Now the biggest benefit of these tests is to check for regressions, i.e. your test suite will tell you if any future change to the pipeline ends up bringing back a previous bug. This will allow you to develop and iterate on code faster, as your test suite can prevent you from introducing breaking changes into a code base, where failing tests should indicate what exactly is going wrong.

Say we have another bug where a newer dataset replaces the "name" column by a "brand" column. We can again write a failing test case first, and then make the appropriate changes to the pipeline.

```python
# test_pipeline.py
mock_cereals_brand_col = mock_cereals.rename({"name": "brand"}, axis=1)


def test_smoke_pipeline_uppercase_cols(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda _: mock_cereals_brand_col)
    best_preworkout_cereal_pipeline.execute_in_process()
```

```python
# pipeline.py
@op
def preprocess_cereals(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.lower()
    
    if "name" not in df.columns:
	    if "brand" in df.columns:
	        df = df.rename({"brand": "name"}, axis=1)
	    else:
	        raise ValueError("df does not contain column 'name'")

    return df
```

> :grey_question: Note
> 
> why raise TODO

As you can see, the tests so far all look similar to one another. We can utilise [`@pytest.mark.parametrize`](https://docs.pytest.org/en/6.2.x/parametrize.html) to create a generalised test function which can be passed all the mocked datasets as parameters.

> :grey_question: Note
> 
> marks TODO

```python
# test_pipeline.py
@pytest.mark.parametrize(
	"df", [mock_cereals, mock_cereals_uppercase_cols, mock_cereals_brand_col]
)
def test_smoke_pipeline(monkeypatch, df):
    monkeypatch.setattr(pd, "read_csv", lambda _: df)
    best_preworkout_cereal_pipeline.execute_in_process()
```

Tests probably don't need as much attention to code quality and maintainability as the code you're actually testing, but it's still a good idea to refactor when it's easy enough to do so.

## 3

Say we want to change the behaviour of our pipeline. Right now we just sort cereals by "protein", but sometimes there are multiple cereals with the same amount of max protein, and we just recommend any one of them arbitrarily (in this case, it's the first record with the max protein that is recommended).

An easy way to differentiate these cereals is by calories, as likely the lower calorie option would be preferred. Let's incorporate this into the pipeline... but remember to write a failing test first!

```python
# test_pipeline.py
from pipeline import find_highest_protein_cereal

...

def test_find_highest_protein_cereal():
    df = pd.DataFrame(
        {
            "name": ["Bran", "Bran - no added sugars", "Honey-comb"],
            "protein": [4, 4, 1],
            "calories": [70, 50, 110],
        }
    )
    assert "Bran - no added sugars" == find_highest_protein_cereal(df)
```

Here we can write a test that actually asserts against the result of the pipeline, or rather the specific function `find_highest_protein_cereal()`. Before we were just seeing if things ran without failures, but now we want to ensure that a feature actually does what we intend. In this case, that's picking "Bran - no added sugars", compared to just "Bran" or "Honey-comb".

```python
$ pytest test_pipeline.py::test_find_highest_protein_cereal -v
===================== test session starts ======================
test_pipeline.py::test_find_highest_protein_cereal FAILED
...
AssertionError: assert 'Bran - no added sugars' == 'Bran'
	- Bran
	+ Bran - no added sugars
```

Our test fails—good! So say our initial idea is to add "calories" to the sorted values in `find_highest_protein_cereal()`,

```diff
 @op
 def find_highest_protein_cereal(df: pd.DataFrame) -> str:
-    sorted_df = df.sort_values("protein", ascending=False)
+    sorted_df = df.sort_values(["protein", "calories"], ascending=False)
     return sorted_df.iloc[0]["name"]
```

and test again,

```python
$ pytest test_pipeline.py::test_find_highest_protein_cereal -v
===================== test session starts ======================
test_pipeline.py::test_find_highest_protein_cereal FAILED
...
AssertionError: assert 'Bran - no added sugars' == 'Bran'
	- Bran
	+ Bran - no added sugars
```

It fails again, which is also good, as it shows we haven't actually fixed what we intended to. In this case we were sorting "calories" in descending order due to the `ascending=False` in [`DataFrame.sort_values()`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html), so to sort by ascending order we can just pass a boolean respectively for each sorted column like so

```diff
- sorted_df = df.sort_values(["protein", "calories"], ascending=False)
+ sorted_df = df.sort_values(["protein", "calories"], ascending=[False, True])
```

```python
$ pytest test_pipeline.py::test_find_highest_protein_cereal -v
===================== test session starts ======================
test_pipeline.py::test_find_highest_protein_cereal PASSED
```