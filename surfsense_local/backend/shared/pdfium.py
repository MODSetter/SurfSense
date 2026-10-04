"""The lock every pdfium call in a process holds: pdfium is not thread-safe.

The API runs tools on a thread pool and Studio runs jobs on several threads, and
pypdfium2 takes no lock of its own.
"""

import threading

lock = threading.Lock()
