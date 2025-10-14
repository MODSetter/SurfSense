# 国产 LLM 配置指南 | Chinese LLM Setup Guide

本指南将帮助你在 SurfSense 中配置和使用国产大语言模型。

This guide helps you configure and use Chinese LLM providers in SurfSense.

---

## 📋 支持的提供商 | Supported Providers

SurfSense 现已支持以下国产 LLM：

- ✅ **DeepSeek** - 国产高性能 AI 模型
- ✅ **阿里通义千问 (Alibaba Qwen)** - 阿里云通义千问大模型
- ✅ **月之暗面 Kimi (Moonshot)** - 月之暗面 Kimi 大模型
- ✅ **智谱 AI GLM (Zhipu)** - 智谱 AI GLM 系列模型

---

## 🚀 快速开始 | Quick Start

### 通用配置步骤 | General Configuration Steps

1. 登录 SurfSense Dashboard
2. 进入 **Settings** → **API Keys** (或 **LLM Configurations**)
3. 点击 **Add New Configuration**
4. 从 **Provider** 下拉菜单中选择你的国产 LLM 提供商
5. 填写必填字段（见下方各提供商详细配置）
6. 点击 **Save**

---

## 1️⃣ DeepSeek 配置 | DeepSeek Configuration

### 获取 API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册并登录账号
3. 进入 **API Keys** 页面
4. 点击 **Create New API Key**
5. 复制生成的 API Key (格式: `sk-xxx`)

### 在 SurfSense 中配置

| 字段 | 值 | 说明 |
|------|-----|------|
| **Configuration Name** | `DeepSeek Chat` | 配置名称（自定义） |
| **Provider** | `DEEPSEEK` | 选择 DeepSeek |
| **Model Name** | `deepseek-chat` | 推荐模型<br>其他选项: `deepseek-coder` |
| **API Key** | `sk-xxx...` | 你的 DeepSeek API Key |
| **API Base URL** | `https://api.deepseek.com` | DeepSeek API 地址 |
| **Parameters** | _(留空)_ | 使用默认参数 |

### 示例配置

```
Configuration Name: DeepSeek Chat
Provider: DEEPSEEK
Model Name: deepseek-chat
API Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
API Base URL: https://api.deepseek.com
```

### 可用模型

- **deepseek-chat**: 通用对话模型（推荐）
- **deepseek-coder**: 代码专用模型

### 定价
- 请访问 [DeepSeek 定价页面](https://platform.deepseek.com/pricing) 查看最新价格

---

## 2️⃣ 阿里通义千问 (Alibaba Qwen) 配置

### 获取 API Key

1. 访问 [阿里云百炼平台](https://dashscope.aliyun.com/)
2. 登录阿里云账号
3. 开通 DashScope 服务
4. 进入 **API-KEY 管理**
5. 创建并复制 API Key

### 在 SurfSense 中配置

| 字段 | 值 | 说明 |
|------|-----|------|
| **Configuration Name** | `通义千问 Max` | 配置名称（自定义） |
| **Provider** | `ALIBABA_QWEN` | 选择阿里通义千问 |
| **Model Name** | `qwen-max` | 推荐模型<br>其他选项: `qwen-plus`, `qwen-turbo` |
| **API Key** | `sk-xxx...` | 你的 DashScope API Key |
| **API Base URL** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云 API 地址 |
| **Parameters** | _(留空)_ | 使用默认参数 |

### 示例配置

```
Configuration Name: 通义千问 Max
Provider: ALIBABA_QWEN
Model Name: qwen-max
API Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
API Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 可用模型

- **qwen-max**: 最强性能，适合复杂任务
- **qwen-plus**: 性价比高，适合日常使用（推荐）
- **qwen-turbo**: 速度快，适合简单任务

### 定价
- 请访问 [阿里云百炼定价](https://help.aliyun.com/zh/model-studio/getting-started/billing) 查看最新价格

---

## 3️⃣ 月之暗面 Kimi (Moonshot) 配置

### 获取 API Key

1. 访问 [Moonshot AI 开放平台](https://platform.moonshot.cn/)
2. 注册并登录账号
3. 进入 **API Key 管理**
4. 创建新的 API Key
5. 复制 API Key

### 在 SurfSense 中配置

| 字段 | 值 | 说明 |
|------|-----|------|
| **Configuration Name** | `Kimi` | 配置名称（自定义） |
| **Provider** | `MOONSHOT` | 选择月之暗面 Kimi |
| **Model Name** | `moonshot-v1-32k` | 推荐模型<br>其他选项: `moonshot-v1-8k`, `moonshot-v1-128k` |
| **API Key** | `sk-xxx...` | 你的 Moonshot API Key |
| **API Base URL** | `https://api.moonshot.cn/v1` | Moonshot API 地址 |
| **Parameters** | _(留空)_ | 使用默认参数 |

### 示例配置

```
Configuration Name: Kimi 32K
Provider: MOONSHOT
Model Name: moonshot-v1-32k
API Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
API Base URL: https://api.moonshot.cn/v1
```

### 可用模型

- **moonshot-v1-8k**: 8K 上下文（基础版）
- **moonshot-v1-32k**: 32K 上下文（推荐）
- **moonshot-v1-128k**: 128K 上下文（长文本专用）

### 定价
- 请访问 [Moonshot AI 定价](https://platform.moonshot.cn/pricing) 查看最新价格

---

## 4️⃣ 智谱 AI GLM (Zhipu) 配置

### 获取 API Key

1. 访问 [智谱 AI 开放平台](https://open.bigmodel.cn/)
2. 注册并登录账号
3. 进入 **API 管理**
4. 创建新的 API Key
5. 复制 API Key

### 在 SurfSense 中配置

| 字段 | 值 | 说明 |
|------|-----|------|
| **Configuration Name** | `GLM-4` | 配置名称（自定义） |
| **Provider** | `ZHIPU` | 选择智谱 AI |
| **Model Name** | `glm-4` | 推荐模型<br>其他选项: `glm-4-flash`, `glm-3-turbo` |
| **API Key** | `xxx.yyy...` | 你的智谱 API Key |
| **API Base URL** | `https://open.bigmodel.cn/api/paas/v4` | 智谱 API 地址 |
| **Parameters** | _(留空)_ | 使用默认参数 |

### 示例配置

```
Configuration Name: GLM-4
Provider: ZHIPU
Model Name: glm-4
API Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxx
API Base URL: https://open.bigmodel.cn/api/paas/v4
```

### 可用模型

- **glm-4**: GLM-4 旗舰模型（推荐）
- **glm-4-flash**: 快速推理版本
- **glm-3-turbo**: 高性价比版本

### 定价
- 请访问 [智谱 AI 定价](https://open.bigmodel.cn/pricing) 查看最新价格

---

## ⚙️ 高级配置 | Advanced Configuration

### 自定义参数 | Custom Parameters

你可以在 **Parameters** 字段中添加自定义参数（JSON 格式）：

```json
{
  "temperature": 0.7,
  "max_tokens": 2000,
  "top_p": 0.9
}
```

### 常用参数说明

| 参数 | 说明 | 默认值 | 范围 |
|------|------|--------|------|
| `temperature` | 控制输出随机性，越高越随机 | 0.7 | 0.0 - 1.0 |
| `max_tokens` | 最大输出 Token 数 | 模型默认 | 1 - 模型上限 |
| `top_p` | 核采样参数 | 1.0 | 0.0 - 1.0 |

---

## 🔧 故障排除 | Troubleshooting

### 常见问题

#### 1. **错误: "Invalid API Key"**
- ✅ 检查 API Key 是否正确复制（无多余空格）
- ✅ 确认 API Key 是否已激活
- ✅ 检查账户余额是否充足

#### 2. **错误: "Connection timeout"**
- ✅ 确认 API Base URL 是否正确
- ✅ 检查网络连接
- ✅ 确认防火墙是否允许访问

#### 3. **错误: "Model not found"**
- ✅ 确认模型名称是否拼写正确
- ✅ 检查该模型是否已开通
- ✅ 参照上方文档确认可用模型名称

#### 4. **文档处理卡住 (IN_PROGRESS)**
- ✅ 检查模型名称中是否有多余空格
- ✅ 确认 API Key 有效且有额度
- ✅ 查看后端日志: `docker compose logs backend`

### 查看日志

```bash
# 查看后端日志
docker compose logs backend --tail 100

# 实时查看日志
docker compose logs -f backend

# 搜索错误
docker compose logs backend | grep -i "error"
```

---

## 💡 最佳实践 | Best Practices

### 1. 模型选择建议

| 任务类型 | 推荐模型 | 说明 |
|---------|---------|------|
| **文档摘要** | Qwen-Plus, GLM-4 | 平衡性能和成本 |
| **代码分析** | DeepSeek-Coder | 代码专用 |
| **长文本处理** | Kimi 128K | 超长上下文 |
| **快速响应** | Qwen-Turbo, GLM-4-Flash | 速度优先 |

### 2. 成本优化

- 🎯 **Long Context LLM**: 使用 Qwen-Plus 或 GLM-4（处理文档摘要）
- ⚡ **Fast LLM**: 使用 Qwen-Turbo 或 GLM-4-Flash（快速对话）
- 🧠 **Strategic LLM**: 使用 Qwen-Max 或 DeepSeek-Chat（复杂推理）

### 3. API Key 安全

- ❌ 不要在公开代码中硬编码 API Key
- ✅ 定期轮换 API Key
- ✅ 为不同用途创建不同的 Key
- ✅ 设置合理的额度限制

---

## 📚 相关资源 | Resources

### 官方文档

- [DeepSeek 文档](https://platform.deepseek.com/docs)
- [阿里云百炼文档](https://help.aliyun.com/zh/model-studio/)
- [Moonshot AI 文档](https://platform.moonshot.cn/docs)
- [智谱 AI 文档](https://open.bigmodel.cn/dev/api)

### SurfSense 文档

- [安装指南](../README.md)
- [贡献指南](../CONTRIBUTING.md)
- [部署指南](../DEPLOYMENT_GUIDE.md)

---

## 🆘 需要帮助？ | Need Help?

如果遇到问题，可以通过以下方式获取帮助：

- 💬 [GitHub Issues](https://github.com/MODSetter/SurfSense/issues)
- 💬 [Discord Community](https://discord.gg/ejRNvftDp9)
- 📧 Email: [项目维护者邮箱]

---

## 🔄 更新日志 | Changelog

- **2025-01-12**: 初始版本，添加 DeepSeek、Qwen、Kimi、GLM 支持

---

**祝你使用愉快！Happy coding with Chinese LLMs! 🚀**

