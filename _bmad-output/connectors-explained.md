# Giải Thích Hệ Thống Connectors

**Tài liệu bổ sung cho SurfSense**

---

## 📌 Connectors Là Gì?

**Connectors** (Bộ kết nối) là tính năng cho phép SurfSense **tìm kiếm và truy xuất dữ liệu từ các ứng dụng bên ngoài** mà bạn đang sử dụng hàng ngày, như:

- 📧 **Gmail** - Tìm kiếm trong emails
- 📁 **Google Drive** - Tìm kiếm files và documents
- 📅 **Google Calendar** - Tìm kiếm events và meetings
- 💬 **Slack** - Tìm kiếm messages và conversations
- 📝 **Notion** - Tìm kiếm pages và databases
- 🎯 **Linear** - Tìm kiếm issues và projects
- 📊 **Airtable** - Tìm kiếm bases và records
- 🎫 **Jira** - Tìm kiếm tickets
- 📚 **Confluence** - Tìm kiếm wiki pages
- 🗂️ **Microsoft Teams** - Tìm kiếm chats và files
- 💰 **DexScreener** - Theo dõi giá token crypto và trading pairs

**Tổng cộng:** SurfSense hỗ trợ **27+ connectors** khác nhau!

---

## 🎯 Mục Đích

Thay vì phải:
1. Mở Gmail → tìm kiếm email
2. Mở Google Drive → tìm kiếm file
3. Mở Slack → tìm kiếm message
4. Mở Notion → tìm kiếm note

Bạn chỉ cần:
- **Mở SurfSense** → Tìm kiếm 1 lần → Nhận kết quả từ **TẤT CẢ** các ứng dụng đã kết nối!

---

## 🔌 Cách Hoạt Động

### Bước 1: Kết Nối (Connect)

Khi bạn click nút **"Connect"** bên cạnh một connector (ví dụ: Google Drive):

1. **OAuth Authentication:**
   - SurfSense chuyển hướng bạn đến trang đăng nhập của Google
   - Bạn đăng nhập và cấp quyền cho SurfSense:
     - ✅ Đọc files trong Drive
     - ✅ Đọc metadata (tên file, ngày tạo, etc.)
     - ❌ **KHÔNG** có quyền xóa hoặc chỉnh sửa files

2. **Lưu Access Token:**
   - Google trả về một **access token** (mã truy cập)
   - SurfSense lưu token này vào database (được mã hóa)
   - Token này cho phép SurfSense truy cập Drive của bạn **thay mặt bạn**

3. **Tạo Connector Record:**
   - SurfSense tạo 1 record trong bảng `search_source_connectors`:
     ```json
     {
       "id": 123,
       "name": "My Google Drive",
       "connector_type": "GOOGLE_DRIVE_CONNECTOR",
       "user_id": "your-user-id",
       "search_space_id": 1,
       "config": {
         "access_token": "encrypted_token",
         "refresh_token": "encrypted_refresh_token"
       },
       "is_indexable": true,
       "periodic_indexing_enabled": true,
       "indexing_frequency_minutes": 60
     }
     ```

### Bước 2: Indexing (Lập Chỉ Mục)

Sau khi kết nối thành công, SurfSense bắt đầu **indexing** (lập chỉ mục) dữ liệu:

1. **Fetch Data từ API:**
   - SurfSense gọi API của Google Drive (sử dụng access token)
   - Lấy danh sách tất cả files: `GET https://www.googleapis.com/drive/v3/files`
   - Với mỗi file, lấy:
     - Tên file
     - Nội dung (text content)
     - Metadata (owner, created_at, modified_at, etc.)

2. **Tạo Embeddings:**
   - Nội dung file được chuyển thành **vector embeddings** (dùng OpenAI/Gemini)
   - Ví dụ: File "Project Plan.docx" → Vector 1536 chiều
   - Vector này biểu diễn **ý nghĩa ngữ nghĩa** của nội dung

3. **Lưu vào Database:**
   - **PostgreSQL** (bảng `documents`):
     ```sql
     INSERT INTO documents (
       title, content, document_type, source_connector_id, user_id
     ) VALUES (
       'Project Plan.docx',
       'Full text content...',
       'GOOGLE_DRIVE_FILE',
       123,  -- connector_id
       'your-user-id'
     );
     ```
   
   - **Vector Database** (Qdrant):
     ```json
     {
       "id": "doc-456",
       "vector": [0.123, -0.456, 0.789, ...],  // 1536 dimensions
       "payload": {
         "title": "Project Plan.docx",
         "document_id": 456,
         "connector_type": "GOOGLE_DRIVE_FILE"
       }
     }
     ```

4. **Periodic Re-indexing:**
   - Mỗi 60 phút (hoặc theo cấu hình), SurfSense tự động:
     - Kiểm tra files mới
     - Kiểm tra files đã update
     - Re-index nếu có thay đổi

### Bước 3: Search (Tìm Kiếm)

Khi bạn tìm kiếm trong SurfSense:

1. **User Query:**
   - Bạn nhập: *"project timeline for Q1"*

2. **Query Embedding:**
   - SurfSense chuyển query thành vector: `[0.234, -0.567, ...]`

3. **Vector Search:**
   - Tìm kiếm trong Qdrant (similarity search):
     ```python
     results = qdrant_client.search(
       collection_name="surfsense",
       query_vector=[0.234, -0.567, ...],
       limit=10,
       filter={
         "user_id": "your-user-id",
         "connector_type": ["GOOGLE_DRIVE_FILE", "GMAIL", "NOTION"]
       }
     )
     ```

4. **Kết Quả:**
   - Trả về top 10 documents có vector gần nhất (most similar)
   - Ví dụ:
     ```
     1. "Q1 Project Timeline.xlsx" (Google Drive) - 95% match
     2. "Email: Q1 Planning Meeting" (Gmail) - 87% match
     3. "Notion: Q1 Roadmap" (Notion) - 82% match
     ```

5. **AI Chat (Optional):**
   - Nếu bạn dùng AI Chat, SurfSense sẽ:
     - Lấy nội dung của top 10 results
     - Gửi cho LLM (GPT-4/Claude/Gemini) kèm theo query
     - LLM tổng hợp và trả lời câu hỏi dựa trên context

---

## 🔐 Bảo Mật

### Quyền Truy Cập

- **Read-only:** Connectors chỉ có quyền **ĐỌC**, không thể xóa/sửa dữ liệu
- **User-scoped:** Mỗi user chỉ thấy dữ liệu của chính họ
- **Encrypted:** Access tokens được mã hóa trong database

### Revoke Access (Thu Hồi Quyền)

Bạn có thể ngắt kết nối bất cứ lúc nào:

1. **Trong SurfSense:**
   - Vào **Settings** → **Connectors**
   - Click **"Disconnect"** bên cạnh connector
   - SurfSense sẽ:
     - Xóa access token
     - Xóa tất cả indexed data từ connector đó

2. **Trong Google/Slack/etc:**
   - Vào settings của ứng dụng gốc
   - Revoke quyền truy cập của SurfSense
   - Ví dụ Google: https://myaccount.google.com/permissions

---

## 📊 Loại Connectors

### 1. Managed OAuth (Composio)

**Ví dụ:** Google Drive, Gmail, Google Calendar

- Sử dụng **Composio** (third-party OAuth provider)
- Ưu điểm:
  - Setup nhanh (không cần tạo OAuth app riêng)
  - Composio quản lý token refresh tự động
- Nhược điểm:
  - Phụ thuộc vào Composio service

**Flow:**
```
User → SurfSense → Composio → Google OAuth → Access Token → SurfSense
```

### 2. Quick Connect (Direct OAuth)

**Ví dụ:** Notion, Slack, Linear, Airtable

- Kết nối trực tiếp với API của ứng dụng
- Ưu điểm:
  - Không phụ thuộc third-party
  - Full control
- Nhược điểm:
  - Cần setup OAuth app riêng cho mỗi service

**Flow:**
```
User → SurfSense → Notion OAuth → Access Token → SurfSense
```

### 3. API Key Based

**Ví dụ:** Elasticsearch, Webcrawler

- Không dùng OAuth, chỉ cần API key
- User nhập API key trực tiếp vào SurfSense

### 4. Self-Hosted Only

**Ví dụ:** Obsidian Connector

- Chỉ hoạt động khi SurfSense chạy self-hosted
- Truy cập trực tiếp vào local file system

### 5. API-Based (No Authentication)

**Ví dụ:** DexScreener Connector

- Không cần OAuth hay API key (public API)
- User chỉ cần cấu hình tokens muốn theo dõi
- Ưu điểm:
  - Setup cực kỳ đơn giản (không cần đăng ký API key)
  - Miễn phí hoàn toàn
  - Real-time data từ public blockchain
- Nhược điểm:
  - Bị giới hạn rate limit của public API
  - Không có personalized data

**Flow:**
```
User → Nhập token addresses → SurfSense → DexScreener Public API → Token Price Data
```

**Use Case:**
- Theo dõi giá crypto tokens (WETH, USDC, etc.)
- Phân tích trading pairs trên các DEX
- AI có thể trả lời: *"What's the current price of WETH?"*

---

## 🛠️ Cấu Hình Connector

Mỗi connector có các settings:

### Indexing Settings

```json
{
  "periodic_indexing_enabled": true,
  "indexing_frequency_minutes": 60,
  "next_scheduled_at": "2026-01-31T15:00:00Z"
}
```

- **periodic_indexing_enabled:** Bật/tắt auto re-index
- **indexing_frequency_minutes:** Tần suất re-index (phút)
- **next_scheduled_at:** Lần re-index tiếp theo

### Connector-Specific Config

**Google Drive:**
```json
{
  "folders": ["folder-id-1", "folder-id-2"],  // Chỉ index các folders này
  "file_types": ["document", "spreadsheet"],  // Chỉ index loại files này
  "exclude_shared": false  // Index cả shared files
}
```

**Slack:**
```json
{
  "channels": ["general", "engineering"],  // Chỉ index các channels này
  "include_dms": true,  // Index direct messages
  "date_range_days": 90  // Chỉ index 90 ngày gần nhất
}
```

**DexScreener:**
```json
{
  "tokens": [
    {
      "chain": "ethereum",
      "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "name": "WETH"
    },
    {
      "chain": "bsc", 
      "address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
      "name": "WBNB"
    }
  ]
}
```

---

## 💡 Use Cases

### 1. Knowledge Worker

**Scenario:** Bạn là Product Manager, cần tìm thông tin về feature request từ khách hàng.

**Trước khi có Connectors:**
- Tìm trong Gmail → Không thấy
- Tìm trong Slack → Không thấy
- Tìm trong Notion → Không thấy
- Tìm trong Linear → Tìm thấy!
- **Tổng thời gian:** 15 phút

**Sau khi có Connectors:**
- Mở SurfSense → Tìm kiếm: *"customer feature request payment"*
- Kết quả:
  1. Linear Issue #123
  2. Slack message từ customer
  3. Email thread với customer
  4. Notion doc: Feature Spec
- **Tổng thời gian:** 30 giây

### 2. Developer

**Scenario:** Debug lỗi production, cần tìm code changes liên quan.

**Connectors kết nối:**
- GitHub (code commits)
- Slack (engineering channel)
- Jira (bug tickets)
- Confluence (technical docs)

**Search query:** *"payment API timeout error"*

**Kết quả:**
1. GitHub commit: "Fix payment timeout"
2. Jira ticket: PROD-456
3. Slack discussion về issue
4. Confluence: Payment API Architecture

### 3. Crypto Trader

**Scenario:** Theo dõi giá token và phân tích market trends.

**Connectors kết nối:**
- DexScreener (token prices và trading pairs)
- Twitter/X (crypto news - nếu có connector)
- Notion (trading notes)

**Search query trong AI Chat:** *"What's the current price of WETH and how has it changed in the last 24 hours?"*

**Kết quả:**
- AI trả lời với real-time price data từ DexScreener
- Hiển thị price changes (5m, 1h, 24h)
- Liquidity và volume information
- Citations link đến DexScreener pairs

---

## 🚨 Lưu Ý Quan Trọng

### 1. Research Mode KHÔNG Tồn Tại Trên FE

**Sự thật:**
- Tài liệu trước đó (user-guide.md) đề cập "Research Mode" là **SAI**
- Frontend chỉ có **1 chế độ chat duy nhất**
- Backend có thể có logic khác nhau, nhưng user không thấy toggle nào

**Đã sửa:** Tài liệu sẽ được cập nhật để loại bỏ phần Research Mode.

### 2. Connector ≠ Extension

- **Browser Extension:** Capture nội dung từ trang web bạn đang browse
- **Connectors:** Fetch dữ liệu từ các ứng dụng bên ngoài (Gmail, Drive, etc.)
- Hai tính năng **độc lập** nhưng **bổ sung** cho nhau

### 3. Privacy

- Dữ liệu được index **chỉ dành cho bạn**
- Không ai khác (kể cả admin) có thể thấy nội dung files của bạn
- Trừ khi bạn share chat với visibility = "SEARCH_SPACE"

---

## 📞 Troubleshooting

### Connector Không Hoạt Động

**Triệu chứng:** Sau khi connect, không thấy kết quả khi search.

**Kiểm tra:**

1. **Indexing status:**
   ```sql
   SELECT name, connector_type, last_indexed_at, next_scheduled_at
   FROM search_source_connectors
   WHERE user_id = 'your-user-id';
   ```
   - Nếu `last_indexed_at` = NULL → Indexing chưa chạy

2. **Backend logs:**
   ```bash
   grep "connector" surfsense_backend/logs/app.log
   ```
   - Tìm lỗi liên quan đến connector

3. **Token expired:**
   - Access token có thể hết hạn
   - Disconnect và reconnect lại connector

### Kết Quả Không Chính Xác

**Nguyên nhân:**
- Embeddings không capture đúng ý nghĩa
- Cần re-index với model tốt hơn

**Giải pháp:**
- Admin có thể trigger manual re-index:
  ```bash
  python manage.py reindex-connector --connector-id 123
  ```

---

**Cập nhật:** 2026-01-31 | **Version:** 1.0
