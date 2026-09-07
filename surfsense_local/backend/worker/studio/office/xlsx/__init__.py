from worker.studio.office.spec import Office, load_skill

xlsx = Office(
    key="xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ext="xlsx",
    stem="workbook",
    label="Excel workbook",
    library="xlsxwriter",
    skill=load_skill(__package__),
)
