import ssl

import httpx

LLAMACLOUD_MAX_RETRIES = 5
LLAMACLOUD_BASE_DELAY = 10
LLAMACLOUD_MAX_DELAY = 120
LLAMACLOUD_RETRYABLE_EXCEPTIONS = (
    ssl.SSLError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
    httpx.LocalProtocolError,
    ConnectionError,
    ConnectionResetError,
    TimeoutError,
    OSError,
)

UPLOAD_BYTES_PER_SECOND_SLOW = 100 * 1024
MIN_UPLOAD_TIMEOUT = 120
MAX_UPLOAD_TIMEOUT = 1800
BASE_JOB_TIMEOUT = 600
PER_PAGE_JOB_TIMEOUT = 60


def calculate_upload_timeout(file_size_bytes: int) -> float:
    estimated_time = (file_size_bytes / UPLOAD_BYTES_PER_SECOND_SLOW) * 1.5
    return max(MIN_UPLOAD_TIMEOUT, min(estimated_time, MAX_UPLOAD_TIMEOUT))


def calculate_job_timeout(estimated_pages: int, file_size_bytes: int) -> float:
    page_based_timeout = BASE_JOB_TIMEOUT + (estimated_pages * PER_PAGE_JOB_TIMEOUT)
    size_based_timeout = BASE_JOB_TIMEOUT + (file_size_bytes / (10 * 1024 * 1024)) * 60
    return max(page_based_timeout, size_based_timeout)
