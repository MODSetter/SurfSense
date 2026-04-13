# SurfSense: Sơ đồ chi tiết các Luồng Ẩn (Triển khai Sâu)

Dựa trên việc kiểm tra sâu cấu trúc database (`db.py`) và kiến trúc API, đây là các Luồng Vi mô (Micro Flows) diễn ra bên dưới bề nổi bổ sung thêm cho 4 luồng cơ bản ban đầu. Đây là các Flow cấu thành sức mạnh hệ sinh thái nền tảng của SurfSense.

---

## 5. Luồng Đồng bộ Thời gian thực & Local-first (RociCorp Zero)
Giao diện của SurfSense đạt được tốc độ phản hồi tính bằng mili-giây (Instant UI) nhờ vào công nghệ Local-first từ Zero.

```mermaid
sequenceDiagram
    participant User as Nguoi Dung
    participant NextJS as NextJS Client (Z-Store)
    participant Zero as Zero Cache Server
    participant Postgres as PostgreSQL DB

    %% Trang thai offline hoac low-latency
    User->>NextJS: Tao Search Space moi
    activate NextJS
    NextJS->>NextJS: Ghi vao IndexedDB (Local)
    NextJS-->>User: [UI] Cap nhat ngay lap tuc (0 latency)
    
    %% Dong bo background
    NextJS->>Zero: Day Mutator (Sync)
    deactivate NextJS
    
    activate Zero
    Zero->>Postgres: Luu thay đoi vao DB trung tam
    Postgres-->>Zero: Xac nhan luu thanh cong
    
    %% Nguoi dung khac trong cung Search Space
    Zero->>NextJS: Ban Replication Subscriptions (Socket)
    deactivate Zero
    activate NextJS
    NextJS->>NextJS: Cap nhat Z-Store cho User B
    deactivate NextJS
```

---

## 6. Luồng Uỷ quyền và Nuốt Dữ liệu từ App Thứ 3 (Third-Party Connectors)
Quy trình nhập liệu từ các nền tảng SaaS (Notion, Google Drive, Jira...) sử dụng Composio và Custom Extractors.

```mermaid
sequenceDiagram
    participant User as Nguoi Dung
    participant Web as Web UI
    participant Backend as FastAPI
    participant Auth as Composio OAuth
    participant 3rdParty as Notion/Drive/Jira
    participant Celery as ETL Celery Workers

    User->>Web: Bam ket noi "Notion"
    Web->>Backend: Yeu cau Authorization URL
    Backend->>Auth: Tao Phien ung dung (Session)
    Auth-->>User: Chuyen huong sang trang OAuth cua Notion
    
    User->>3rdParty: Dong y cap quyen đoc
    3rdParty-->>Backend: Callback Redirect voi Auth Code
    activate Backend
    Backend->>Auth: Đoi Code lay Access Token
    Auth-->>Backend: Tra ve Token
    Backend->>Backend: Luu vao Search Space DB
    deactivate Backend
    
    %% Kich hoat Ingestion
    Backend->>Celery: Giao nhiem vu Crawl API (Task)
    activate Celery
    Celery->>3rdParty: Pull hang loat Docs / Tickets
    3rdParty-->>Celery: Tra ve JSON data
    Celery->>Celery: Convert JSON -> Markdown -> Chunks
    Celery->>Celery: Luu VectorDB
    Celery-->>Web: Notification: "Dong bo Notion hoan tat"
    deactivate Celery
```

---

## 7. Luồng Giao tiếp Cộng tác & Bình luận (Collaboration / Chat Comments)
Mỗi Search Space trong SurfSense là một "Phòng làm việc chung". Các đoạn Chat AI có thể được bình luận, chia sẻ.

```mermaid
sequenceDiagram
    participant UserA as Nguoi Dung A
    participant Zero as Zero (Realtime)
    participant DB as Postgres (Chat_Comments)
    participant UserB as Nguoi Dung B

    UserA->>UserA: Mo đoan chat cua Assistant
    UserA->>Zero: Them Comment "@UserB cậu xem đoan nay"
    activate Zero
    Zero->>DB: Luu Comment vao NewChatMessage
    
    %% Tinh nang cap nhat tu đong cho UserB
    DB-->>Zero: State Changed
    Zero-->>UserB: Trigger Sync (Realtime) tang IndexedDB
    deactivate Zero
    
    activate UserB
    UserB->>UserB: Thay notification Mention tren UI
    UserB->>Zero: Reply lai Comment
    deactivate UserB
```

---

## 8. Luồng Phát sinh Nội dung Đa phương tiện từ RAG (Podcast / Video)
Trình độ tổng hợp kiến thức của SurfSense không dừng ở đoạn text, mà còn mở rộng ra Audio, Podcasts, Video Presentation dựa trên DB Models.

```mermaid
sequenceDiagram
    participant User as Nguoi Dung
    participant Web as Web UI
    participant API as FastAPI
    participant Celery as Celery Tasks
    participant GenAI as Audio/Video Gen AI
    participant DB as Postgres

    User->>Web: "Tao Podcast ve chu đe bao cao thang nay"
    activate Web
    Web->>API: POST /api/generate-podcast
    deactivate Web
    
    activate API
    API->>DB: Tao ban ghi PodcastStatus = PENDING
    API->>Celery: Send task `generate_podcast`
    API-->>Web: Tra ve Job ID
    deactivate API
    
    activate Celery
    Celery->>DB: Update PodcastStatus = GENERATING
    Celery->>GenAI: Truyen RAG content & Yeu cau sinh giong noi
    activate GenAI
    GenAI-->>Celery: Tra ve Stream/File URL (Media)
    deactivate GenAI
    
    Celery->>DB: Update PodcastStatus = READY & Luu Media Path
    deactivate Celery
    
    %% Cap nhat UI qua Zero
    DB-->>Zero: State Mutation
    Zero-->>Web: Giao dien hien thi Audio Player
```
