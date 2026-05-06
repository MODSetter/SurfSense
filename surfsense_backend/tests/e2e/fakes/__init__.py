"""Strict fakes for third-party SDKs, used in E2E mode only.

Every fake here implements __getattr__ that raises NotImplementedError
on any unknown surface. Combined with sys.modules-level hijacking in
run_backend.py / run_celery.py, this makes silent pass-through to the
real SDK impossible: a future production code path that introduces a
new SDK call site fails CI with a clear "add this to the fake" message.
"""
