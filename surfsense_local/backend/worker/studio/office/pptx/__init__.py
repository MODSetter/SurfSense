from worker.studio.office.spec import Office, load_skill

pptx = Office(
    key="pptx",
    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ext="pptx",
    stem="deck",
    label="PowerPoint deck",
    library="python-pptx",
    skill=load_skill(__package__),
)
