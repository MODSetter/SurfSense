"""The frozen worker reads a web page as the plugins worker does for Add from the web.

trafilatura opens its settings.cfg by path, its fallback jusText every stoplist,
and courlan tld's copy of the public suffix list; no hook collects them, so a
frozen worker without them fails every link added from the web, and only there.
"""

import json
import sys
from pathlib import Path

import pytest

from tests.packaging.frozen_backend import frozen_backend
from worker.document_script.run import run_document_script

pytestmark = pytest.mark.packaging

READ_A_PAGE = r"""
import json, os
from pathlib import Path

import curl_cffi.requests
from justext import get_stoplist
from tld import get_tld

from modules.documents.web_sources.page_reading.page_text import page_text

paragraph = "<p>The moon pulls the sea towards it, and the sea rises in a bulge.</p>"
html = (
    "<html><head><title>Tides explained</title></head><body><article>"
    "<h1>Tides explained</h1>" + paragraph * 30 + "</article></body></html>"
)
pulled = page_text(html, "https://tides.example/explained")
Path(os.environ["OUTPUT_PATH"]).write_text(json.dumps({
    "title": pulled.title,
    "text": "The moon pulls the sea" in pulled.markdown,
    "stoplist": len(get_stoplist("English")),
    "domain": get_tld("https://www.example.co.uk", as_object=True).fld,
}))
"""


@pytest.fixture(scope="module")
def frozen(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The backend frozen once for this module."""
    return frozen_backend(tmp_path_factory.mktemp("frozen-backend"))


def test_the_frozen_worker_reads_a_page_with_its_data_files(
    frozen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The page's title and text come back, read with every data file in place."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(frozen))

    result = run_document_script(
        READ_A_PAGE, output_name="page.json", images={}, timeout_seconds=600
    )

    assert result.ok, result.traceback_tail
    report = json.loads(result.output or b"{}")
    assert report == {
        "title": "Tides explained",
        "text": True,
        "stoplist": report["stoplist"],
        "domain": "example.co.uk",
    }
    assert report["stoplist"] > 100
