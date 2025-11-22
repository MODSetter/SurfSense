---
name: Performance & Observability Monitoring
about: Add performance metrics and monitoring infrastructure for production observability
title: 'Add Performance Metrics & Monitoring'
labels: 'observability, performance, infrastructure'
assignees: ''
---

## Summary
Implement comprehensive performance metrics collection and monitoring to proactively identify bottlenecks, track system health, and ensure optimal user experience as usage scales.

## Motivation
As more users and data accumulate, even well-indexed queries or compression workers can become bottlenecks. Proactive monitoring enables:
- **Early Warning**: Detect performance degradation before users complain
- **Capacity Planning**: Understand usage patterns and plan scaling
- **SLA Compliance**: Track and maintain service level objectives
- **Cost Optimization**: Identify and eliminate wasteful operations
- **Root Cause Analysis**: Quickly diagnose production issues

### Current State
- ✅ Application logs exist
- ✅ Database queries are indexed
- ❌ No metrics collection (response times, queue depths, error rates)
- ❌ No dashboards or alerting
- ❌ No performance SLOs defined

## Proposed Implementation

### 1. Metrics Collection (Prometheus)

#### Backend Instrumentation
```python
# surfsense_backend/app/middleware/metrics_middleware.py
from prometheus_client import Counter, Histogram, Gauge
from starlette.middleware.base import BaseHTTPMiddleware
from time import time

# Define metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

compression_queue_size = Gauge(
    'compression_queue_size',
    'Number of files waiting for compression',
    ['type']  # image or video
)

database_connection_pool_size = Gauge(
    'database_connection_pool_size',
    'Active database connections'
)

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time()

        # Process request
        response = await call_next(request)

        # Record metrics
        duration = time() - start_time
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        return response
```

#### Application Metrics
```python
# surfsense_backend/app/utils/metrics.py
from prometheus_client import Counter, Histogram

# Compression metrics
image_compressions_total = Counter(
    'image_compressions_total',
    'Total images compressed',
    ['level', 'status']  # level: low/medium/high, status: success/failure
)

image_compression_duration = Histogram(
    'image_compression_duration_seconds',
    'Image compression duration',
    ['level']
)

video_compressions_total = Counter(
    'video_compressions_total',
    'Total videos compressed',
    ['level', 'status']
)

video_compression_duration = Histogram(
    'video_compression_duration_seconds',
    'Video compression duration',
    ['level']
)

# Search metrics
search_queries_total = Counter(
    'search_queries_total',
    'Total search queries',
    ['search_space_id']
)

search_query_duration = Histogram(
    'search_query_duration_seconds',
    'Search query execution time'
)

# Usage in code
from app.utils.metrics import image_compressions_total, image_compression_duration

async def compress_image(file, level):
    start_time = time()
    try:
        result = await perform_compression(file, level)
        image_compressions_total.labels(level=level, status='success').inc()
        return result
    except Exception as e:
        image_compressions_total.labels(level=level, status='failure').inc()
        raise
    finally:
        duration = time() - start_time
        image_compression_duration.labels(level=level).observe(duration)
```

#### Expose Metrics Endpoint
```python
# surfsense_backend/app/routes/metrics_routes.py
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

router = APIRouter()

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### 2. Metrics Storage & Visualization (Prometheus + Grafana)

#### Prometheus Configuration
```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'surfsense-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/api/v1/metrics'

  - job_name: 'surfsense-db'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'surfsense-redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

#### Docker Compose Integration
```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=secure_password
      - GF_INSTALL_PLUGINS=redis-datasource

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      - DATA_SOURCE_NAME=postgresql://user:pass@postgres:5432/surfsense?sslmode=disable

volumes:
  prometheus-data:
  grafana-data:
```

### 3. Grafana Dashboards

#### Dashboard 1: API Performance
```json
{
  "title": "SurfSense API Performance",
  "panels": [
    {
      "title": "Request Rate",
      "targets": [{
        "expr": "rate(http_requests_total[5m])"
      }]
    },
    {
      "title": "P95 Latency",
      "targets": [{
        "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
      }]
    },
    {
      "title": "Error Rate",
      "targets": [{
        "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
      }]
    }
  ]
}
```

#### Dashboard 2: Compression Performance
- Compression queue size (image/video)
- Compression duration (P50, P95, P99)
- Compression success/failure rate
- Compression ratio distribution

#### Dashboard 3: Database Performance
- Query duration
- Connection pool utilization
- Slow query count (> 1s)
- Deadlock count

### 4. Alerting (Prometheus Alertmanager)

```yaml
# prometheus/alerts.yml
groups:
  - name: performance
    interval: 30s
    rules:
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"
          description: "P95 latency is {{ $value }}s (threshold: 1s)"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} requests/sec"

      - alert: CompressionQueueBacklog
        expr: compression_queue_size > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Compression queue backing up"
          description: "{{ $labels.type }} queue has {{ $value }} items"

      - alert: DatabaseConnectionPoolExhaustion
        expr: database_connection_pool_size > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool nearly exhausted"
          description: "{{ $value }}% of connections in use"
```

## Metrics to Track

### API Performance
- [x] Request rate (requests/sec)
- [x] Request duration (P50, P95, P99)
- [x] Error rate (by endpoint, status code)
- [ ] Payload size (request/response)

### Database
- [ ] Query duration (by query type)
- [ ] Connection pool size
- [ ] Active connections
- [ ] Slow queries (> 1s)
- [ ] Table sizes
- [ ] Index hit ratio

### Compression
- [ ] Queue size (image/video)
- [ ] Processing time (P50, P95, P99)
- [ ] Success/failure rate
- [ ] Compression ratio distribution
- [ ] Disk space used

### System Resources
- [ ] CPU utilization
- [ ] Memory usage
- [ ] Disk I/O
- [ ] Network I/O

### Business Metrics
- [ ] Active users
- [ ] Searches per day
- [ ] Documents indexed
- [ ] Storage used per user

## Acceptance Criteria
- [ ] Prometheus running and collecting metrics
- [ ] Grafana dashboards created and accessible
- [ ] Key endpoints instrumented:
  - `/api/v1/searchspaces`
  - `/api/v1/compress/*`
  - `/api/v1/search`
  - `/api/v1/documents`
- [ ] Alerting configured for:
  - High latency (P95 > 1s)
  - High error rate (> 5%)
  - Queue backlog (> 100 items)
  - Database issues
- [ ] Documentation written for:
  - Accessing dashboards
  - Interpreting metrics
  - Responding to alerts
  - Adding new metrics

## Testing Plan
1. Deploy Prometheus + Grafana stack
2. Configure metrics scraping
3. Generate load to test metrics collection
4. Verify dashboards display data correctly
5. Trigger alerts intentionally (induce high latency)
6. Verify alert notifications work
7. Document runbooks for common alerts

## Documentation Updates
- [ ] Create `docs/MONITORING.md`:
  ```markdown
  # Monitoring & Observability

  ## Accessing Dashboards
  - Grafana: http://localhost:3001 (admin/secure_password)
  - Prometheus: http://localhost:9090

  ## Key Metrics
  - **Request Rate**: Number of API requests per second
  - **Latency**: Time to process requests (P50, P95, P99)
  - **Error Rate**: Percentage of 5xx responses
  - **Queue Size**: Files waiting for compression

  ## Interpreting Dashboards
  [Screenshots and explanations of each dashboard]

  ## Alerting
  Alerts are configured for:
  1. High API latency (P95 > 1s for 5+ minutes)
  2. High error rate (> 5% for 5+ minutes)
  3. Compression queue backlog (> 100 items for 10+ minutes)

  ## Adding New Metrics
  [Guide for developers to add instrumentation]
  ```
- [ ] Add monitoring section to `README.md`
- [ ] Document alert runbooks

## Architecture Impact
- **Medium Impact**: Adds monitoring infrastructure
- **Performance**: < 1% overhead from metrics collection
- **Dependencies**: Prometheus, Grafana (optional but recommended)
- **Storage**: ~500MB/month for metrics (30-day retention)

## Related Issues/PRs
- Addresses continuous improvement recommendation #5
- Enables proactive performance optimization
- Supports capacity planning

## Priority
**Medium** - Not critical for MVP but essential for production

## Effort Estimate
- **Infrastructure Setup**: 6-8 hours
- **Metrics Instrumentation**: 12-16 hours
- **Dashboard Creation**: 8-10 hours
- **Alerting Configuration**: 4-6 hours
- **Documentation**: 4-6 hours
- **Testing & Tuning**: 6-8 hours
- **Total**: 2-3 weeks

## References
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [FastAPI Prometheus Middleware](https://github.com/stephenhillier/starlette_prometheus)
- [The RED Method](https://www.weave.works/blog/the-red-method-key-metrics-for-microservices-architecture/) (Rate, Errors, Duration)
- [The USE Method](http://www.brendangregg.com/usemethod.html) (Utilization, Saturation, Errors)
