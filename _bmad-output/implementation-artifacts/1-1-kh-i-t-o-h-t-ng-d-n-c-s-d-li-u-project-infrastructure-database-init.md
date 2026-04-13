# Story 1.1: Khởi tạo Hạ tầng Dự án & Cơ sở Dữ liệu (Project Infrastructure & Database Init)

**Status:** done

## PRD Requirements
As a Kỹ sư Hệ thống,
I want thiết lập bộ khung Next.js, FastAPI, và cấu hình Docker-compose cho Postgres/Redis/ZeroServer,
So that toàn bộ nền tảng có thể khởi chạy môi trường phát triển (Dev Environment) một cách nhất quán cho tất cả các team.
**Acceptance Criteria:**
**Given** môi trường dự án mới
**When** chạy lệnh `docker-compose -f docker/docker-compose.dev.yml up -d`
**Then** các containers Postgres 16 (với pgvector), Redis, Zero-Server, FastAPI, và Next.js khởi tạo thành công
**And** database tự động migrate được schema ban đầu bao gồm bảng `users` với quy tắc `snake_case`.

## Architecture Compliance & As-Built Context
> *This section is automatically generated to map implemented components to this story's requirements.*

This story has been successfully implemented in the brownfield codebase. The following key files contain the core logic for this feature:

- `surfsense_backend/app/schemas/auth.py`
- `surfsense_backend/app/agents/new_chat/tools/mcp_tool.py`
- `surfsense_backend/app/services/linear/__init__.py`
- `surfsense_backend/app/services/vision_autocomplete_service.py`
- `surfsense_backend/app/etl_pipeline/parsers/vision_llm.py`
- `surfsense_backend/app/agents/new_chat/tools/jira/update_issue.py`
- `surfsense_backend/app/connectors/teams_connector.py`
- `surfsense_backend/app/utils/rbac.py`

## Implementation Notes
- **UI/UX**: Needs to follow `surfsense_web` React/Tailwind standards.
- **Backend**: Needs to follow `surfsense_backend` FastAPI standards.
