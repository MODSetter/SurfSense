# Deferred Work

## Deferred from: code review of story 3-5-model-selection-via-quota (2026-04-14)

- **stripe_subscription_id has no unique constraint** [surfsense_backend/app/db.py] — Column added without UNIQUE constraint. Should be enforced once Stripe integration (Epic 5) is implemented to prevent duplicate subscription mappings.
- **load_llm_config_from_yaml reads API keys directly from YAML file, not env vars** [surfsense_backend/app/config.py] — Pre-existing: YAML config stores API keys inline. Spec Task 1.2 says "đọc API keys từ env vars" but this is the existing pattern used throughout the project. To be refactored when security hardening is prioritized.
