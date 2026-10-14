---
name: surfsense-data
description: Work out numbers from spreadsheet and CSV sources (.xlsx, .csv, .tsv) by writing a pandas script that surfsense_analyze_data runs: totals, averages, trends, rankings, comparisons, cleaning, and charts that can go into a document. Load it whenever the user asks for figures from a table, or a chart of one.
---

# Analysing spreadsheets and CSVs

You answer a question about a table by writing a Python script and passing it to `surfsense_analyze_data` with the sources it reads. SurfSense runs the script on copies of those files and returns what it printed, the tables it saved and the charts it drew. You then answer from those results, or place a chart in a document.

## Analyse or read

- Analyse when the answer needs arithmetic over rows: sums, counts, averages, growth, shares, rankings, grouping, joining two tables, finding gaps or outliers, or a chart.
- Read the source's text in `sources/` instead when the question is what a table says, a handful of cells, or the prose around it.
- Do not add up a long column yourself from the text: run the analysis. The text in `sources/` is an extract made for reading; the script reads the file itself.
- Only spreadsheet and CSV sources the user selected can be analysed. A PDF or Word table is read from its text.

## The contract

- `os.environ["INPUT_DIR"]` holds a read-only copy of each source you named, under its own file name. `manifest.json` in the same folder lists each file with its `document_id` and `title`, so you can say which source a number came from. Nothing the script does reaches the user's files.
- Save what you make in `os.environ["OUTPUT_DIR"]`: tables as `.csv`, charts as `.png`. Only `.csv`, `.tsv`, `.png`, `.jpg`, `.svg`, `.xlsx`, `.json` and `.txt` files at the top of that folder are kept, at most 20. Spaces and other characters in a file name become `_`.
- Use pandas, numpy, matplotlib, openpyxl and Python's standard library. Do not use the network.
- The script runs alone, from an empty folder, for at most 120 seconds. Each run starts fresh: nothing from an earlier run is in `INPUT_DIR`.

## Loading each format

- `.csv`: `pd.read_csv(path)`. If everything lands in one column, the file uses semicolons: pass `sep=";"`. Numbers written as `1,234` need `thousands=","`. A file that will not decode needs `encoding="latin-1"`.
- `.tsv`: `pd.read_csv(path, sep="\t")`.
- `.xlsx`: `pd.read_excel(path, sheet_name=None)` gives every sheet as a dict of frames; look at the names before you pick one. When the header is not on the first row, pass `header=<row index>` or `skiprows`.
- When you do not know the layout yet, make the first run a look: print `df.shape`, `df.columns.tolist()` and `df.head().to_string()`, then write the real analysis.
- Clean before you compute: `df.columns = df.columns.str.strip()`, `pd.to_numeric(df[col], errors="coerce")` for numbers stored as text, `pd.to_datetime(df[col], errors="coerce")` for dates, and drop a total row the sheet already has so it is not counted twice.

## Printing results

- Print only what answers the question: the figures, labelled, or a small table with `.to_string(index=False)`. Printed output past 6,000 characters is cut, so never print a whole frame.
- Round for reading (`round(2)`), keep units and currencies, and say how many rows were left out by cleaning.
- Name the source with each figure, from the manifest's `title`.

## Saving tables and charts

- A table: `df.to_csv(os.path.join(os.environ["OUTPUT_DIR"], "name.csv"), index=False)`. The result shows its first 20 rows and 8 columns; the file keeps all of it.
- A chart: one matplotlib figure per chart, with a title, axis labels with units and readable tick labels. Call `fig.tight_layout()`, save with `fig.savefig(path, dpi=150)`, then `plt.close(fig)`.
- Bars for comparing groups, lines for change over time. Sort bars by value unless the categories have their own order, such as months.
- Chart only numbers the data holds.

## Using a chart in a document

- The result names each chart, `analysis-<run>-<name>`. Load the surfsense-documents skill, list that name in `surfsense_render_document`'s `images`, and open it in the document script at `IMAGES_DIR/<name>.png`, as you would a source's figure.
- Write the figures in the document from what the analysis printed, not from the chart.
- A chart stays in this chat's `outputs/analysis/<run>/`; only documents rendered in this chat can place it.

## When a run fails

- The result gives the error and the lines that led to it. A `KeyError` usually means a column is named differently: print `df.columns.tolist()`. A `ValueError` while converting means text in a number column: use `errors="coerce"`.
- Fix the script and run it again. If this is your third failed run for this request, stop and tell the user what failed.

## Example: Totals by group with a chart

```python
import json
import os

import matplotlib.pyplot as plt
import pandas as pd

input_dir = os.environ["INPUT_DIR"]
output_dir = os.environ["OUTPUT_DIR"]
with open(os.path.join(input_dir, "manifest.json"), encoding="utf-8") as listed:
    source = json.load(listed)[0]

sales = pd.read_csv(os.path.join(input_dir, source["file"]))
sales.columns = sales.columns.str.strip()
sales["revenue"] = pd.to_numeric(sales["revenue"], errors="coerce")
dropped = int(sales["revenue"].isna().sum())
sales = sales.dropna(subset=["revenue"])

by_region = (
    sales.groupby("region", as_index=False)["revenue"]
    .sum()
    .sort_values("revenue", ascending=False)
)
print(f"Source: {source['title']}")
print(by_region.to_string(index=False))
print(f"Rows without a revenue figure, left out: {dropped}")
by_region.to_csv(os.path.join(output_dir, "revenue_by_region.csv"), index=False)

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(by_region["region"], by_region["revenue"])
ax.set_title("Revenue by region")
ax.set_ylabel("Revenue")
fig.tight_layout()
fig.savefig(os.path.join(output_dir, "revenue_by_region.png"), dpi=150)
plt.close(fig)
```

## Example: Every sheet of a workbook

```python
import json
import os

import pandas as pd

input_dir = os.environ["INPUT_DIR"]
with open(os.path.join(input_dir, "manifest.json"), encoding="utf-8") as listed:
    sources = json.load(listed)

for source in sources:
    if not source["file"].lower().endswith(".xlsx"):
        continue
    sheets = pd.read_excel(os.path.join(input_dir, source["file"]), sheet_name=None)
    for name, sheet in sheets.items():
        print(f"{source['title']} / {name}: {sheet.shape[0]} rows, columns {list(sheet.columns)}")
        print(sheet.head(5).to_string(index=False))
```
