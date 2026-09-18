FROM keygen/api:v1.7.2

EXPOSE 3000

# 127.0.0.1, not localhost: that resolves to ::1 here and Puma binds 0.0.0.0.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/v1/health || exit 1
