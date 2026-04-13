# SurfSense: Chi tiết Micro User Flows

Dưới đây là sơ đồ chi tiết (Micro Flows) phân tách sâu vào 4 tính năng lõi quan trọng nhất của hệ thống, bao phủ cả trải nghiệm người dùng lẫn luồng dữ liệu ngầm phía sau. 

---

## 1. Luồng Tự động Nhập dữ liệu (Local-First Ingestion)
Đây là "vũ khí bí mật" của SurfSense. Thay vì bắt user bấm nút upload thủ công, hệ thống sử dụng Desktop App và Extension để tự động hóa việc đưa tài liệu vào ngữ cảnh của AI.

```mermaid
sequenceDiagram
    participant User as Nguoi Dung
    participant Desk as Desktop App (Watcher)
    participant Ext as Browser Extension
    participant API as Backend API
    participant ETL as ETL & Indexing Pipeline

    %% Desktop Sync
    User->>Desk: Luu file PDF/Doc vao thu muc "SurfSense"
    activate Desk
    Desk->>Desk: Phat hien file moi (chokidar)
    Desk->>API: Upload file background
    deactivate Desk

    %% Extension Sync
    User->>Ext: Chon "Luu vao SurfSense" khi dang doc bao
    activate Ext
    Ext->>Ext: Dung content.ts trich xuat HTML/Text
    Ext->>API: Gui data qua API
    deactivate Ext

    %% Processing
    activate API
    API->>ETL: Chuyen Job vao Hang doi Celery
    deactivate API
    
    activate ETL
    ETL->>ETL: Parsing (Tach van ban)
    ETL->>ETL: Chunking (Chia nho doan)
    ETL->>ETL: Embedding (Vector hoa)
    ETL-->>User: [UI notification] "Tai lieu da san sang đe hoi đap!"
    deactivate ETL
```

---

## 2. Luồng Trò chuyện & Truy xuất (Core Analytical Chat - RAG)
Đây là tính năng tương tác chính trên Website, nơi người dùng đặt câu hỏi và AI tìm kiếm bối cảnh từ dữ liệu cá nhân của user. 

```mermaid
sequenceDiagram
    participant User as Nguoi Dung
    participant Web as Web (surfsense_web)
    participant API as FastAPI Backend
    participant RAG as Retriever (Vector DB)
    participant LLM as AI Agents

    User->>Web: Nhap cau hoi: "Tom tat cho toi file Report"
    activate Web
    Web->>API: POST /api/chat
    activate API
    
    API->>RAG: Truy van Vector (Semantic Search)
    activate RAG
    RAG-->>API: Tra ve Top-K chunks & Metadata
    deactivate RAG

    API->>LLM: Chuyen Cau hoi + Context cho Agent
    activate LLM
    LLM-->>API: Stream tokens (Co danh dau Citation)
    deactivate LLM
    
    API-->>Web: SSE (Server-Sent Events) Stream
    deactivate API
    
    Web->>Web: Parse token & Hien thi tin nhan AI
    Web->>Web: Thay Citation [1], [2] -> Hien thi tai lieu o Split-Pane
    Web-->>User: Đoc tra loi va bam vao Citation đe xem source
    deactivate Web
```

---

## 3. Luồng Hỏi Đáp Thần Tốc (Desktop Quick Ask)
Một tính năng nổi bật giúp SurfSense gắn chặt vào thói quen hàng ngày của User. Bất kể đang mở app nào, user chỉ cần bấm tổ hợp phím là có thể truy vấn mọi tài liệu.

```mermaid
sequenceDiagram
    participant OS as He đieu hanh
    participant Tray as Desktop Tray & Shortcuts
    participant QA as Quick Ask Overlay
    participant API as Backend API

    User->>OS: Bam to hop (VD: Cmd/Ctrl + Shift + Space)
    OS->>Tray: Kich hoat Global Shortcut
    activate Tray
    Tray->>QA: Hien thi khung tim kiem noi (Spotlight)
    deactivate Tray
    
    activate QA
    QA-->>User: San sang nhan Text
    User->>QA: Nhap nhanh: "Tai lieu doanh thu nam ngoai đe o đau?"
    QA->>API: Goi API chat nhanh
    activate API
    API-->>QA: Stream cau tra loi + ten file
    deactivate API
    QA-->>User: Tra ket qua tuc thi
    
    %% Tuy chon
    User->>QA: Click Open in App
    QA->>OS: Mo Surfsense Web hoac App chinh tung ung
    deactivate QA
```

---

## 4. Luồng Chuyển giao Xác thực (Cross-Platform Auth)
Vì Web đóng vai trò là Hub chính, Desktop App cần cơ chế mượn xác thực từ Web một cách mượt mà và an toàn.

```mermaid
sequenceDiagram
    participant User as Nguoi Dung
    participant Desk as Desktop App
    participant Web as Web App
    participant API as Backend API

    User->>Desk: Mo App lan đau
    activate Desk
    Desk-->>User: Hien "Login with Browser"
    User->>Desk: Bấm Login
    Desk->>Web: Mo trinh duyet voi Deep Link (schema: surfsense://)
    deactivate Desk
    
    activate Web
    Web->>Web: Kiem tra Session/Cookies
    alt Neu chua login
        Web-->>User: Mo trang /login > Nhap tai khoan > Thanh cong
    end
    Web->>API: Tao Token phien lam viec
    API-->>Web: Tra ve Token an toan
    Web->>Desk: Chuyen huong ve surfsense://auth?token=...
    deactivate Web
    
    activate Desk
    Desk->>Desk: Luu Token vao Keychain/Secure Storage
    Desk-->>User: Chua san sang, chuyen sang man hinh Permissions
    User->>Desk: Cap quyen đoc thu muc (Mac/Win)
    Desk-->>User: "San sang đong bo!"
    deactivate Desk
```

---

*Ghi chú: Toàn bộ biểu đồ đã được biên dịch không chứa dấu tiếng Việt bên trong logic sơ đồ để đảm bảo khả năng tương thích hiển thị tuyệt đối.*
