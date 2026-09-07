from io import BytesIO

from worker.studio.builders.types import Builder, Built, Source
from worker.studio.builders.util import as_list, as_text, parse_json, slug

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "sheets": '
    '[{"name": str, "columns": [str], "rows": [[str, ...]]}]}.'
)


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Focus on: {user_prompt}." if user_prompt else ""
    return (
        "Extract the sources below into one or more tables, using their facts "
        "only." + focus + " " + _SCHEMA
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Workbook"
    sheets = [s for s in as_list(spec.get("sheets")) if isinstance(s, dict)]
    if not sheets:
        sheets = [{"name": "Sheet1", "columns": [], "rows": []}]

    import xlsxwriter

    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    lines = [f"# {title}"]

    for index, sheet in enumerate(sheets):
        name = as_text(sheet.get("name")) or f"Sheet{index + 1}"
        worksheet = workbook.add_worksheet(name[:31])  # Excel caps sheet names.
        columns = [as_text(column) for column in as_list(sheet.get("columns"))]
        header = workbook.add_format({"bold": True})

        lines.append(f"\n## {name}")
        for column, label in enumerate(columns):
            worksheet.write(0, column, label, header)
        if columns:
            lines.append("| " + " | ".join(columns) + " |")

        for row_index, row in enumerate(as_list(sheet.get("rows")), start=1):
            cells = [as_text(cell) for cell in as_list(row)]
            for column, value in enumerate(cells):
                worksheet.write(row_index, column, value)
            if cells:
                lines.append("| " + " | ".join(cells) + " |")

    workbook.close()
    return Built(
        title=title,
        markdown="\n".join(lines),
        primary=buffer.getvalue(),
        primary_mime=MIME,
        primary_filename=f"{slug(title, 'workbook')}.xlsx",
    )


xlsx = Builder(key="xlsx", prompt=prompt, build=build)
