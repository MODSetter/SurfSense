# TrollLLM — Hướng dẫn tích hợp vào SurfSense

## Base URL
- OpenAI-compatible endpoint: `https://chat.trollllm.xyz/v1`
- Anthropic-compatible endpoint: `https://chat.trollllm.xyz` (không có /v1)

## Danh sách model chính xác (tên phải đúng 100%)
| Model ID | Provider | Ghi chú |
|---|---|---|
| `claude-haiku-4.5` | Anthropic | Speed |
| `claude-sonnet-4` | Anthropic | Balanced |
| `claude-sonnet-4.5` | Anthropic | Balanced |
| `claude-sonnet-4.6` | Anthropic | Balanced |
| `claude-opus-4.5` | Anthropic | Reasoning |
| `claude-opus-4.6` | Anthropic | Reasoning |
| `gemini-3-flash-preview` | Google | Speed (**KHÔNG phải** gemini-3-flash) |
| `gemini-3.1-pro-preview` | Google | Multimodal |
| `gpt-5.2` | OpenAI | Reasoning |
| `gpt-5.4` | OpenAI | Reasoning |
| `gpt-5.2-codex` | OpenAI | Code |
| `gpt-5.3-codex` | OpenAI | Code |

## Cách add model vào SurfSense (đúng cách)

### Cách 1 — Dùng Provider = OPENAI (khuyến nghị, dùng cho mọi model)
- **LLM Provider**: `OPENAI`
- **Model Name**: tên chính xác từ bảng trên (ví dụ `claude-sonnet-4.6`)
- **API Key**: TrollLLM API key
- **API Base URL**: `https://chat.trollllm.xyz/v1`

### Cách 2 — Dùng Custom Provider (LiteLLM format)
- **LLM Provider**: `Custom Provider`
- **Custom Provider Name**: tùy ý (ví dụ `trollllm`)
- **Model Name**: phải có prefix `openai/` → `openai/claude-sonnet-4.6`
- **API Key**: TrollLLM API key
- **API Base URL**: `https://chat.trollllm.xyz/v1`

## Lỗi phổ biến
1. **Tên model sai**: `gemini-3-flash` ❌ → phải là `gemini-3-flash-preview` ✅
2. **Custom Provider thiếu prefix**: `gemini-3-flash-preview` ❌ → `openai/gemini-3-flash-preview` ✅
3. **Base URL sai**: `https://trollllm.xyz/v1` ❌ → `https://chat.trollllm.xyz/v1` ✅

## Lưu ý đặc biệt
- TrollLLM yêu cầu `User-Agent` header để bypass Cloudflare, nhưng SurfSense/LiteLLM thường tự set header này.
- Nếu dùng Anthropic SDK format: dùng `x-api-key` header thay vì `Authorization: Bearer`.
