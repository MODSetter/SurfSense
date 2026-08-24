from app.file_storage.backends.azure import AzureBlobBackend


async def _chunks():
    yield b"abc"
    yield b"def"


class FakeDownloader:
    async def chunks(self):
        yield b"bc"
        yield b"de"


class FakeBlob:
    def __init__(self):
        self.uploaded = b""
        self.download_args = None

    async def upload_blob(self, chunks, **_kwargs):
        self.uploaded = b"".join([chunk async for chunk in chunks])

    async def download_blob(self, **kwargs):
        self.download_args = kwargs
        return FakeDownloader()


class FakeService:
    def __init__(self, blob):
        self.blob = blob

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def get_blob_client(self, _container, _key):
        return self.blob


async def test_azure_backend_streams_upload_and_range(monkeypatch):
    backend = AzureBlobBackend(connection_string="unused", container="artifacts")
    blob = FakeBlob()
    monkeypatch.setattr(backend, "_service", lambda: FakeService(blob))

    await backend.put_stream("out.mp4", _chunks(), content_type="video/mp4")
    ranged = b"".join([chunk async for chunk in backend.open_range("out.mp4", 1, 4)])

    assert blob.uploaded == b"abcdef"
    assert blob.download_args == {"offset": 1, "length": 4}
    assert ranged == b"bcde"
