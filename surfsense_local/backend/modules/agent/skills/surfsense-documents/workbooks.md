# Excel workbooks

A workbook is a script that writes xlsxwriter or openpyxl itself and saves at `os.environ["OUTPUT_PATH"]`; the `surfsense_docs` helper does not make one. Follow [`SKILL.md`](SKILL.md) for rendering, changing and failed runs; this file is what is particular to workbooks.

- Write numbers as numbers, never as text, and give them a number format: thousands separators, currency, percentages, dates.
- Give each sheet a header row in a bold format, column widths that fit the content (`set_column`), and freeze the header (`freeze_panes(1, 0)`).
- Where the user means a total, an average or any value computed from other cells, write a formula rather than a number you worked out, so it stays right when they change the data. Pass the value it comes to after the format, `write_formula("B14", "=SUM(B2:B13)", money, 1520)`: xlsxwriter stores 0 otherwise, and Studio's viewer shows the stored value. With Office support on, LibreOffice recalculates the workbook after the run and stores its own values in their place; the result says which happened.
- A chart is a native Excel chart (`add_chart`, then `insert_chart` beside the data), drawn from the cells.
- Name sheets after what they hold. Keep one table per sheet, starting at A1.

## Checking a workbook

A workbook has no previews: its result is a summary of each sheet, its used range, its first rows and the formulas found. Check that every sheet is there, the headers and values sit in the right columns, and each total is a formula given the value it comes to. When the result says LibreOffice recalculated the workbook, a formula's cell in the rows shows its computed value, saved in the file, and the formulas are listed below: check those totals make sense. A formula it left blank had an error or a function LibreOffice lacks; fix it. When the result says the values were not recalculated, a formula shows as written, not its value.

## Example: Excel

```python
import os

import xlsxwriter

rows = [("Pilot", 12000, 0.1), ("Rollout", 48000, 0.15), ("Support", 6000, 0.05)]

book = xlsxwriter.Workbook(os.environ["OUTPUT_PATH"])
sheet = book.add_worksheet("Costs")
header = book.add_format({"bold": True, "bottom": 1, "bg_color": "#DDE6F0"})
money = book.add_format({"num_format": "#,##0 [$EUR]"})
percent = book.add_format({"num_format": "0%"})
bold_money = book.add_format({"bold": True, "num_format": "#,##0 [$EUR]"})

sheet.write_row(0, 0, ["Phase", "Cost", "Contingency", "With contingency"], header)
for r, (phase, cost, contingency) in enumerate(rows, start=1):
    sheet.write(r, 0, phase)
    sheet.write_number(r, 1, cost, money)
    sheet.write_number(r, 2, contingency, percent)
    # The last argument is the value shown until the file is recalculated.
    sheet.write_formula(
        r, 3, f"=B{r + 1}*(1+C{r + 1})", money, cost * (1 + contingency)
    )
total = len(rows) + 1
sheet.write(total, 0, "Total", header)
cost_total = sum(cost for _, cost, _ in rows)
with_contingency = sum(cost * (1 + contingency) for _, cost, contingency in rows)
sheet.write_formula(total, 1, f"=SUM(B2:B{total})", bold_money, cost_total)
sheet.write_formula(total, 3, f"=SUM(D2:D{total})", bold_money, with_contingency)
sheet.set_column(0, 0, 14)
sheet.set_column(1, 3, 18)
sheet.freeze_panes(1, 0)

chart = book.add_chart({"type": "column"})
chart.add_series(
    {
        "name": "Cost",
        "categories": ["Costs", 1, 0, len(rows), 0],
        "values": ["Costs", 1, 1, len(rows), 1],
    }
)
chart.set_title({"name": "Cost by phase"})
chart.set_legend({"none": True})
sheet.insert_chart("F2", chart)
book.close()
```
