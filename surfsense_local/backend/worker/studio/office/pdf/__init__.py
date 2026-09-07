from worker.studio.office.spec import Office, load_skill

pdf = Office(
    key="pdf",
    mime="application/pdf",
    ext="pdf",
    stem="document",
    label="PDF document",
    library="reportlab",
    skill=load_skill(__package__),
)
