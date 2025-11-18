# Ollama Memory Optimization Guide for SurfSense

This guide helps you optimize Ollama configuration for memory-constrained VPS environments.

## Quick Recommendations

### For VPS with 4GB RAM or less

Use **highly quantized small models**:

```yaml
# global_llm_config.yaml
global_llm_configs:
  - id: -1
    name: "Ollama Qwen2.5 3B (Q4)"
    provider: "OLLAMA"
    model_name: "qwen2.5:3b-instruct-q4_K_M"
    api_key: ""
    api_base: "http://localhost:11434"
    language: "English"
    litellm_params:
      temperature: 0.7
      max_tokens: 2048
      num_ctx: 2048  # Reduced context window
```

**Recommended models:**
- `qwen2.5:3b-instruct-q4_K_M` (~2GB RAM)
- `gemma2:2b-instruct-q4_K_M` (~1.5GB RAM)
- `phi3:mini-4k-instruct-q4_K_M` (~2GB RAM)

### For VPS with 8GB RAM

Use **medium-sized quantized models**:

```yaml
global_llm_configs:
  - id: -1
    name: "Ollama Llama 3.1 8B (Q4)"
    provider: "OLLAMA"
    model_name: "llama3.1:8b-instruct-q4_K_M"
    api_key: ""
    api_base: "http://localhost:11434"
    language: "English"
    litellm_params:
      temperature: 0.7
      max_tokens: 4096
      num_ctx: 4096  # Moderate context window
```

**Recommended models:**
- `llama3.1:8b-instruct-q4_K_M` (~5GB RAM)
- `mistral:7b-instruct-q4_K_M` (~4GB RAM)
- `qwen2.5:7b-instruct-q4_K_M` (~4.5GB RAM)

### For VPS with 16GB+ RAM

Use **larger models with better quantization**:

```yaml
global_llm_configs:
  - id: -1
    name: "Ollama Llama 3.1 8B (Q8)"
    provider: "OLLAMA"
    model_name: "llama3.1:8b-instruct-q8_0"
    api_key: ""
    api_base: "http://localhost:11434"
    language: "English"
    litellm_params:
      temperature: 0.7
      max_tokens: 8192
      num_ctx: 8192
```

---

## Memory Optimization Techniques

### 1. Reduce Context Window Size

The context window (`num_ctx`) directly impacts memory usage. Reduce it for memory savings:

```yaml
litellm_params:
  num_ctx: 2048  # Default is often 4096 or 8192
```

**Memory impact:**
- 4096 context: ~2x memory of 2048
- 8192 context: ~4x memory of 2048

### 2. Use Quantized Models

Quantization reduces model precision to save memory:

| Quantization | Quality | Memory | Recommendation |
|-------------|---------|--------|----------------|
| Q8_0 | Highest | 8-bit | Best quality if RAM allows |
| Q5_K_M | High | 5-bit | Good balance |
| Q4_K_M | Medium | 4-bit | **Recommended for VPS** |
| Q3_K_M | Lower | 3-bit | Maximum memory savings |
| Q2_K | Lowest | 2-bit | Not recommended |

### 3. Configure Ollama Environment Variables

Create or edit `/etc/systemd/system/ollama.service.d/override.conf`:

```ini
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=5m"
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**Environment variables explained:**
- `OLLAMA_NUM_PARALLEL=1`: Process one request at a time (saves memory)
- `OLLAMA_MAX_LOADED_MODELS=1`: Keep only one model in memory
- `OLLAMA_KEEP_ALIVE=5m`: Unload model after 5 minutes of inactivity

### 4. Add Swap Space

If you're running low on memory, add swap:

```bash
# Create 4GB swap file
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Optimize swappiness
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

---

## Model Selection Guide

### Best Models for Memory-Constrained Environments

#### Lightweight (1-3GB RAM)
```bash
ollama pull qwen2.5:3b-instruct-q4_K_M
ollama pull gemma2:2b-instruct-q4_K_M
ollama pull phi3:mini-4k-instruct-q4_K_M
```

#### Medium (4-6GB RAM)
```bash
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull mistral:7b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
```

#### Quality (8-12GB RAM)
```bash
ollama pull llama3.1:8b-instruct-q8_0
ollama pull qwen2.5:14b-instruct-q4_K_M
```

### Check Available Models

```bash
# List available models
ollama list

# Check model info (including memory requirements)
ollama show llama3.1:8b-instruct-q4_K_M
```

---

## SurfSense Configuration

### Example: Memory-Optimized Setup

Create `surfsense_backend/app/config/global_llm_config.yaml`:

```yaml
# Memory-optimized Ollama configuration for VPS
global_llm_configs:
  # Long Context LLM - larger context, fewer tokens
  - id: -1
    name: "Ollama Long Context (Local)"
    provider: "OLLAMA"
    model_name: "qwen2.5:7b-instruct-q4_K_M"
    api_key: ""
    api_base: "http://localhost:11434"
    language: "English"
    litellm_params:
      temperature: 0.7
      max_tokens: 2048
      num_ctx: 4096

  # Fast LLM - smaller model, lower latency
  - id: -2
    name: "Ollama Fast (Local)"
    provider: "OLLAMA"
    model_name: "qwen2.5:3b-instruct-q4_K_M"
    api_key: ""
    api_base: "http://localhost:11434"
    language: "English"
    litellm_params:
      temperature: 0.5
      max_tokens: 1024
      num_ctx: 2048

  # Strategic LLM - same as long context
  - id: -3
    name: "Ollama Strategic (Local)"
    provider: "OLLAMA"
    model_name: "qwen2.5:7b-instruct-q4_K_M"
    api_key: ""
    api_base: "http://localhost:11434"
    language: "English"
    litellm_params:
      temperature: 0.3
      max_tokens: 2048
      num_ctx: 4096
```

### Hybrid Configuration (Ollama + Cloud)

For best results with limited RAM, use Ollama for fast queries and cloud APIs for complex tasks:

```yaml
global_llm_configs:
  # Complex tasks - Cloud API (no local memory needed)
  - id: -1
    name: "GPT-4 Turbo (Long Context)"
    provider: "OPENAI"
    model_name: "gpt-4-turbo"
    api_key: "sk-your-api-key"
    api_base: ""
    language: "English"
    litellm_params:
      temperature: 0.7
      max_tokens: 4000

  # Quick queries - Local Ollama (fast, private)
  - id: -2
    name: "Ollama Fast (Local)"
    provider: "OLLAMA"
    model_name: "qwen2.5:3b-instruct-q4_K_M"
    api_key: ""
    api_base: "http://localhost:11434"
    language: "English"
    litellm_params:
      temperature: 0.5
      max_tokens: 1024
      num_ctx: 2048

  # Strategic - Cloud API
  - id: -3
    name: "GPT-4 (Strategic)"
    provider: "OPENAI"
    model_name: "gpt-4"
    api_key: "sk-your-api-key"
    api_base: ""
    language: "English"
    litellm_params:
      temperature: 0.3
      max_tokens: 2000
```

---

## Troubleshooting

### Error: "Out of memory"

1. **Switch to a smaller model**:
   ```bash
   ollama rm llama3.1:8b
   ollama pull qwen2.5:3b-instruct-q4_K_M
   ```

2. **Reduce context window** in your config:
   ```yaml
   litellm_params:
     num_ctx: 2048
   ```

3. **Free up memory**:
   ```bash
   # Stop unnecessary services
   sudo systemctl stop ollama
   free -h
   sudo systemctl start ollama
   ```

4. **Check what's using memory**:
   ```bash
   htop
   # or
   ps aux --sort=-%mem | head -20
   ```

### Error: "Model not found"

Pull the model first:
```bash
ollama pull qwen2.5:3b-instruct-q4_K_M
```

### Slow responses

1. Ensure only one model is loaded:
   ```bash
   export OLLAMA_MAX_LOADED_MODELS=1
   ```

2. Add more swap space

3. Use a faster/smaller model

### Connection refused

Ensure Ollama is running:
```bash
sudo systemctl status ollama
sudo systemctl start ollama
```

Check it's listening:
```bash
curl http://localhost:11434/api/tags
```

---

## Monitoring Memory Usage

### Check Ollama memory usage

```bash
# Watch memory in real-time
watch -n 1 'ps aux | grep ollama'

# Check system memory
free -h

# Detailed memory info
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached"
```

### Log analysis

```bash
# Ollama logs
sudo journalctl -u ollama -f

# System memory pressure
dmesg | grep -i "out of memory"
```

---

## Summary

For a typical VPS with 4-8GB RAM running SurfSense:

1. **Use Q4_K_M quantized models** (best memory/quality balance)
2. **Start with smaller models** (3B-7B parameters)
3. **Reduce context window** to 2048-4096
4. **Configure Ollama** to load only one model at a time
5. **Add swap space** as a safety net
6. **Consider hybrid setup** with cloud APIs for complex tasks

**Recommended starting configuration:**
- Model: `qwen2.5:3b-instruct-q4_K_M` or `qwen2.5:7b-instruct-q4_K_M`
- Context: 2048-4096
- Max tokens: 1024-2048
