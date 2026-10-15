"""A rendered workbook's size agrees with the summary the model reads beside it."""

from io import BytesIO

import pytest
import xlsxwriter

from modules.agent.tool_endpoint.document_size import document_size
from worker.studio.script_document.workbook_summary import workbook_summary

pytestmark = pytest.mark.unit


def test_a_chartsheet_is_counted_as_a_chart_not_a_sheet() -> None:
    """Both said a different number of sheets for one workbook."""
    buffer = BytesIO()
    book = xlsxwriter.Workbook(buffer, {"in_memory": True})
    book.add_worksheet("Costs").write_column(0, 0, [1, 2, 3])
    book.add_worksheet("Notes").write(0, 0, "Figures in EUR")
    chart = book.add_chart({"type": "column"})
    chart.add_series({"values": "=Costs!$A$1:$A$3"})
    book.add_chartsheet("Chart").set_chart(chart)
    book.close()
    data = buffer.getvalue()
    summary = workbook_summary(data)

    assert summary.startswith("A workbook of 2 sheets and 1 chart.")
    assert document_size("xlsx", data, summary) == "2 sheets"
