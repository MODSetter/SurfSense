from worker.studio.office.spec import Office, load_skill

docx = Office(
    key="docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ext="docx",
    stem="document",
    label="Word document",
    library="python-docx",
    skill=load_skill(__package__),
)
