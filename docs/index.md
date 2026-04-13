# SurfSense Project Documentation Index

## 🌟 Project Overview
- **Type:** monorepo with 4 parts
- **Primary Languages:** Python, TypeScript, TSX
- **Architecture:** API Service (FastAPI) + Web App (Next.js App Router) + Desktop + Extension

## 🏗️ Quick Reference

### Frontend (`surfsense_web/`)
- **Type:** web
- **Tech Stack:** Next.js 16 (App Router), React 19, TailwindCSS 4, Drizzle ORM, @rocicorp/zero (Local-first sync)

### Backend (`surfsense_backend/`)
- **Type:** backend
- **Tech Stack:** FastAPI (Python 3.12), SQLAlchemy, Alembic, Celery, Redis, LangGraph, pgvector

### Browser Extension (`surfsense_browser_extension/`)
- **Type:** extension
- **Tech Stack:** React, TypeScript

### Desktop Client (`surfsense_desktop/`)
- **Type:** desktop
- **Tech Stack:** TypeScript (TBD frameworks)

## 🌐 Code Review Graph & Communities
Dự án đã được phân tích bằng công cụ Code Review Graph, trích xuất thành công:
- **6,578 nodes** & **55,487 edges**
- **696 communities/modules** architecture pages (Được lưu ở `.code-review-graph/wiki/`)

## 📑 Generated Documentation

- [Project Overview](./project-overview.md)
- [Architecture (Frontend)](./architecture-web.md)
- [Architecture (Backend)](./architecture-backend.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Component Inventory](./component-inventory.md)
- [Development Guide](./development-guide.md)
- [Deployment Guide](./deployment-guide.md)
- [API Contracts](./api-contracts.md)
- [Data Models](./data-models.md)
- [Integration Architecture](./integration-architecture.md)

## 📁 Existing Documentation
- [Code Review Graph Wiki](../.code-review-graph/wiki/_index.md) - Chi tiết từng community và file dependency.
- [Project Scan Report](./project-scan-report.json) - Trạng thái scan ban đầu của BMad.

## 🚀 Getting Started
Để bắt đầu cài đặt và phát triển trên dự án này:
1. Đọc [Development Guide](./development-guide.md) để biết cách spin up hệ thống Backend (FastAPI, Redis, Celery, Postgres pgvector) và Frontend (Next.js, Zero-Cache) bằng Docker.
2. Tham khảo [Integration Architecture](./integration-architecture.md) để hiểu cách Zero-Cache đồng bộ trạng thái Frontend-Backend và cách Celery Worker xử lý các pipeline lấy dữ liệu bằng LLM.
3. Tham khảo [Architecture (Backend)](./architecture-backend.md) hoặc [Architecture (Frontend)](./architecture-web.md) khi muốn trace sâu vào tầng mã nguồn (EtlPipelineService, HybridSearch, Next App Router, etc.).

---
*This documentation is part of the BMAD generation process.*
