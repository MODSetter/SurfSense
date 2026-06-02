"""Azure Blob Storage backend (the first production target)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.file_storage.backends.base import StorageBackend


class AzureBlobBackend(StorageBackend):
    """Stores objects as blobs in an Azure Blob Storage container."""

    backend_name = "azure"

    def __init__(self, *, connection_string: str, container: str) -> None:
        self._connection_string = connection_string
        self._container = container

    def _service(self):
        from azure.storage.blob.aio import BlobServiceClient

        return BlobServiceClient.from_connection_string(self._connection_string)

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        from azure.storage.blob import ContentSettings

        settings = ContentSettings(content_type=content_type) if content_type else None
        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            await blob.upload_blob(data, overwrite=True, content_settings=settings)

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            downloader = await blob.download_blob()
            async for chunk in downloader.chunks():
                yield chunk

    async def delete(self, key: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            try:
                await blob.delete_blob()
            except ResourceNotFoundError:
                pass

    async def exists(self, key: str) -> bool:
        async with self._service() as service:
            blob = service.get_blob_client(self._container, key)
            return await blob.exists()
