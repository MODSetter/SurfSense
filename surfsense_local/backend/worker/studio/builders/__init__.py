from worker.studio.builder import Builder
from worker.studio.builders.flashcards import flashcards
from worker.studio.builders.html_doc import html_doc
from worker.studio.builders.mindmap import mindmap
from worker.studio.builders.quiz import quiz
from worker.studio.builders.summary import summary

# format key -> builder for the structured formats: the model emits markdown or
# JSON and a small deterministic builder renders it. The other families route
# elsewhere — documents to worker/studio/office/ (model-written code) and audio/
# visual to worker/studio/media/. The API's dependency-free catalog
# (modules/artifacts/formats.py) lists every key; tests/unit/worker/
# test_studio_builders.py asserts the three families partition it.
BUILDERS: dict[str, Builder] = {
    builder.key: builder
    for builder in (
        summary,
        html_doc,
        mindmap,
        flashcards,
        quiz,
    )
}

__all__ = ["BUILDERS"]
