# Scaling Checklist

Concrete techniques for when the complexity checklist in SKILL.md confirms scale is a real problem. Apply in order - each level solves the previous level's bottleneck.

---

## Level 0: Optimize First

Before adding infrastructure, exhaust these:

- [ ] Database queries have proper indexes
- [ ] N+1 queries eliminated
- [ ] Connection pooling configured
- [ ] Slow endpoints profiled and optimized
- [ ] Static assets served via CDN

## Level 1: Read-Heavy

**Symptom**: Database reads are the bottleneck.

| Technique | When | Trade-off |
|-----------|------|-----------|
| Application cache (in-memory) | Small, frequently accessed data | Stale data, memory pressure |
| Redis/Memcached | Shared cache across instances | Network hop, cache invalidation complexity |
| Read replicas | High read volume, slight staleness OK | Replication lag, eventual consistency |
| CDN | Static or semi-static content | Cache invalidation delay |

## Level 2: Write-Heavy

**Symptom**: Database writes or processing are the bottleneck.

| Technique | When | Trade-off |
|-----------|------|-----------|
| Async task queue (Celery, SQS) | Work can be deferred | Eventual consistency, failure handling |
| Write-behind cache | Batch frequent writes | Data loss risk on crash |
| Event streaming (Kafka) | Multiple consumers of same data | Operational complexity, ordering guarantees |
| CQRS | Reads and writes have diverged significantly | Two models to maintain |

## Level 3: Traffic Spikes

**Symptom**: Individual instances can't handle peak load.

| Technique | When | Trade-off |
|-----------|------|-----------|
| Horizontal scaling + load balancer | Stateless services | Session management, deploy complexity |
| Auto-scaling | Unpredictable traffic patterns | Cold start latency, cost spikes |
| Rate limiting | Protect against abuse/spikes | Legitimate users may be throttled |
| Circuit breakers | Downstream services degrade | Partial functionality during failures |

## Level 4: Data Growth

**Symptom**: Single database can't hold or query all the data efficiently.

| Technique | When | Trade-off |
|-----------|------|-----------|
| Table partitioning | Time-series or naturally partitioned data | Query complexity, partition management |
| Archival / cold storage | Old data rarely accessed | Access latency for archived data |
| Database sharding | Partitioning insufficient, clear shard key exists | Cross-shard queries, operational burden |
| Search index (Elasticsearch) | Full-text or complex queries on large datasets | Index lag, another system to operate |

## Level 5: Multi-Region

**Symptom**: Users are geographically distributed, latency matters.

| Technique | When | Trade-off |
|-----------|------|-----------|
| CDN + edge caching | Static/semi-static content | Cache invalidation |
| Read replicas per region | Read-heavy, slight staleness OK | Replication lag |
| Active-passive failover | Disaster recovery | Failover time, cost of standby |
| Active-active multi-region | True global low-latency required | Conflict resolution, extreme complexity |

---

## Decision Rule

Always start at Level 0. Move to the next level only when you have **measured evidence** that the current level is insufficient. Skipping levels is how you end up with Kafka for a TODO app.
