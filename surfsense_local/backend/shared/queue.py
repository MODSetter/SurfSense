from huey import SqliteHuey

from shared.config import get_storage_settings

_settings = get_storage_settings()
# SqliteHuey opens the file as it is constructed.
_settings.data_dir.mkdir(parents=True, exist_ok=True)

# Its own file: the consumer polls constantly, and would otherwise hold the
# write lock against the database serving requests.
huey = SqliteHuey(filename=str(_settings.queue_path))
