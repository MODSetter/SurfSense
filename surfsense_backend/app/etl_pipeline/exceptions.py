class EtlParseError(Exception):
    """Raised when an ETL parser fails to produce content."""


class EtlServiceUnavailableError(Exception):
    """Raised when the configured ETL_SERVICE is not recognised."""


class EtlUnsupportedFileError(Exception):
    """Raised when a file type cannot be parsed by any ETL pipeline."""
