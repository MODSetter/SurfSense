"""Any link no other puller takes: the page's text, read on the user's own connection."""

from urllib.parse import SplitResult, urlsplit

from modules.documents.web_sources.pullers.puller import HostCheck, Pulled, Puller


def _takes(_: SplitResult) -> bool:
    return True


def _hosts(url: str) -> list[str]:
    return [urlsplit(url).hostname or ""]


def _read(url: str, reach: HostCheck) -> Pulled:
    # Imported where a read runs, the plugins worker: the API routes links and
    # never loads trafilatura or curl_cffi to do it.
    from modules.documents.web_sources.page_reading.page_read import read_page

    return read_page(url, reach)


PULLER = Puller(id="web_page", takes=_takes, hosts=_hosts, read=_read)
