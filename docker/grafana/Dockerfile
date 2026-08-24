FROM grafana/otel-lgtm:0.31.0

EXPOSE 3000 4317 4318

HEALTHCHECK --interval=10s --timeout=3s --start-period=45s --retries=18 \
    CMD test -f /tmp/ready
