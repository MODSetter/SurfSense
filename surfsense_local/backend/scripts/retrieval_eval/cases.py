"""The corpus a run indexes, and the queries it asks of it."""

from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter, model_validator

CORPUS_DIR = Path(__file__).with_name("corpus")
QUERIES_PATH = Path(__file__).with_name("queries.json")
# A fetched dataset lands here rather than in the repo: it keeps someone else's
# licence out of our tree, and the eval runs with only the authored corpus when
# it is absent. `scripts/fetch_limit_small.py` writes one.
LOCAL_DIR = Path(__file__).with_name("local")


class Query(BaseModel):
    id: str = Field(min_length=1)
    # What this query is here to measure: english, japanese, identifier, superseded…
    slice: str = Field(min_length=1)
    text: str = Field(min_length=1)
    # A hit answers the query when its passage contains any of these. Text, not
    # chunk ids, so re-chunking or a new embedder does not invalidate the file.
    expect: list[str] = Field(min_length=1)


class Document(BaseModel):
    title: str
    markdown: str


def load_queries(path: Path = QUERIES_PATH) -> list[Query]:
    queries = TypeAdapter(list[Query]).validate_json(path.read_bytes())
    if len({query.id for query in queries}) != len(queries):
        raise ValueError("a query id is listed twice")
    return queries


def load_corpus(directory: Path = CORPUS_DIR) -> list[Document]:
    """Every markdown file in the corpus, titled by its filename."""
    files = sorted(directory.glob("*.md"))
    if not files:
        raise ValueError(f"no corpus in {directory}")
    return [
        Document(title=path.stem, markdown=path.read_text(encoding="utf-8"))
        for path in files
    ]


class Corpus(BaseModel):
    """The two halves together, checked against each other before a run."""

    documents: list[Document]
    queries: list[Query]

    @model_validator(mode="after")
    def _every_query_is_answerable(self) -> "Corpus":
        # A typo in `expect` would otherwise read as a retrieval failure.
        haystack = "\n".join(
            document.markdown for document in self.documents
        ).casefold()
        for query in self.queries:
            if not any(phrase.casefold() in haystack for phrase in query.expect):
                raise ValueError(f"{query.id}: no document contains what it expects")
        return self


def load(
    directory: Path = CORPUS_DIR,
    queries_path: Path = QUERIES_PATH,
    local_dir: Path | None = LOCAL_DIR,
) -> Corpus:
    """The authored corpus, plus any fetched dataset sitting beside it."""
    documents = load_corpus(directory)
    queries = load_queries(queries_path)
    if local_dir and (local_dir / "corpus").is_dir():
        documents += load_corpus(local_dir / "corpus")
    if local_dir and (local_dir / "queries.json").is_file():
        queries += load_queries(local_dir / "queries.json")
    return Corpus(documents=documents, queries=queries)
