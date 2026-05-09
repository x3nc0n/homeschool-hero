# Ray AG-06 Performance Strategy

- **Author:** Ray
- **Context:** Gradebook, compliance, and pacing endpoints recomputed expensive payloads on repeated reads, and assignment/grade search paths lacked several query-specific indexes.
- **Decision:** Use app-local TTL caching with explicit prefix invalidation on relevant writes, add conditional GET headers for cacheable computed reads, and ship composite/partial/PostgreSQL full-text indexes aligned to the dominant family/student/subject query patterns.
- **Impact:** Hot read paths are cheaper without changing API semantics, stale computed results are bounded by explicit invalidation + short TTLs, and production PostgreSQL deployments gain the new index coverage through Alembic.
