# Local LLM Installation Guide

Complete guide for deploying SurfSense with local Ollama models (Mistral NeMo + TildeOpen).

## Prerequisites

### Hardware Requirements
- **RAM**: 32GB+ recommended (minimum 24GB)
- **Disk Space**: 50GB+ free space
- **CPU**: Modern multi-core processor (GPU optional but not required)
- **Network**: Stable internet for initial model downloads

### Software Requirements
- **OS**: Ubuntu 20.04+, Debian 11+, or similar Linux distribution
- **Python**: 3.10 or higher
- **Node.js**: 18+ (for frontend)
- **Git**: For repository management

## Installation Steps

### Step 1: Install Ollama

Ollama provides local LLM inference with automatic model management.

```bash
# Download and install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Enable Ollama service to start on boot
sudo systemctl enable ollama

# Start Ollama service
sudo systemctl start ollama

# Verify Ollama is running
sudo systemctl status ollama

# Test Ollama API
curl http://localhost:11434/api/tags
```

**Expected output**: JSON response with empty model list (we'll add models next).

### Step 2: Download Required Models

Download Mistral NeMo (7.1GB) and TildeOpen (21GB).

```bash
# Download Mistral NeMo base model
ollama pull mistral-nemo

# This will take 5-10 minutes depending on your connection
# Progress will be shown in the terminal

# Download TildeOpen Latvian model
ollama pull tildeopen:30b-q5_k_m

# This will take 10-20 minutes (21GB download)

# Verify models are installed
ollama list
```

**Expected output**:
```
NAME                   ID              SIZE      MODIFIED
mistral-nemo:latest    e7e06d107c6c    7.1 GB    X minutes ago
tildeopen:30b-q5_k_m   7f0adb68ec7d    21 GB     X minutes ago
```

### Step 3: Create Optimized Mistral NeMo Model

The default mistral-nemo has a 4K context window. We need to create a custom version with 128K context.

```bash
# Create Modelfile for 128K context
cat > /tmp/mistral-nemo-128k.modelfile << 'EOF'
FROM mistral-nemo:latest

# Set context window to 128K tokens (Mistral NeMo maximum)
PARAMETER num_ctx 131072

# Keep other parameters optimized for RAG
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
EOF

# Create the custom model
ollama create mistral-nemo:128k -f /tmp/mistral-nemo-128k.modelfile

# Verify the model was created
ollama list | grep "128k"
```

**Expected output**:
```
mistral-nemo:128k      7d56f30917ac    7.1 GB    X seconds ago
```

### Step 4: Verify Model Configuration

Test that the 128K context is properly configured.

```bash
# Check the model configuration
ollama show mistral-nemo:128k --modelfile | grep num_ctx
```

**Expected output**:
```
PARAMETER num_ctx 131072
```

### Step 5: Configure SurfSense Backend

Navigate to your SurfSense backend directory and configure the LLM settings.

```bash
# Navigate to backend config directory
cd /opt/SurfSense/surfsense_backend/app/config

# Copy the template to create your config
cp global_llm_config.yaml.template global_llm_config.yaml

# Edit the config file
nano global_llm_config.yaml
```

**Replace the placeholder with your actual Gemini API key**:
```yaml
api_key: "${GEMINI_API_KEY}"  # Change this line
```

**To**:
```yaml
api_key: "your_actual_gemini_api_key_here"
```

**Save and exit** (Ctrl+X, then Y, then Enter in nano).

### Step 6: Update Backend Code

The backend needs two Python files patched to handle the correct context window.

#### Patch 1: `/opt/SurfSense/surfsense_backend/app/agents/researcher/utils.py`

Find the `get_model_context_window()` function and update it:

```python
def get_model_context_window(model_name: str) -> int:
    """Get the total context window size for a model (input + output tokens)."""

    # Override for Ollama models with known incorrect LiteLLM values
    if "mistral-nemo" in model_name.lower():
        return 131072  # Mistral NeMo actual context window: 128K tokens

    try:
        model_info = get_model_info(model_name)
        context_window = model_info.get("max_input_tokens", 4096)
        return context_window
    except Exception as e:
        print(
            f"Warning: Could not get model info for {model_name}, using default 4096 tokens. Error: {e}"
        )
        return 4096
```

#### Patch 2: `/opt/SurfSense/surfsense_backend/app/utils/document_converters.py`

Apply the same change to the `get_model_context_window()` function in this file.

**Or use this automated script**:

```bash
# Automated patching script
cd /opt/SurfSense/surfsense_backend

# Backup original files
cp app/agents/researcher/utils.py app/agents/researcher/utils.py.backup
cp app/utils/document_converters.py app/utils/document_converters.py.backup

# Apply patches (download from repository or apply manually)
# See MIGRATION_LOCAL_LLM.md for detailed patch content
```

### Step 7: Set Environment Variables

Ensure your environment has the necessary variables.

```bash
# Edit backend environment file
nano /opt/SurfSense/surfsense_backend/.env
```

**Add or verify these lines**:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
```

### Step 8: Restart Services

Restart all SurfSense services to apply changes.

```bash
# Restart backend
sudo systemctl restart surfsense

# Restart frontend (if separate service)
sudo systemctl restart surfsense-frontend

# Restart Celery workers
sudo systemctl restart surfsense-celery

# Restart Celery beat
sudo systemctl restart surfsense-celery-beat

# Wait a few seconds for services to start
sleep 10
```

### Step 9: Verify Services

Check that all services started successfully.

```bash
# Check Ollama
systemctl status ollama | head -10

# Check SurfSense backend
systemctl status surfsense | head -10

# Check frontend
systemctl status surfsense-frontend | head -10

# Check Celery
systemctl status surfsense-celery | head -10

# Test Ollama API
curl http://localhost:11434/api/tags

# Test backend health endpoint
curl http://localhost:8000/health
```

**All services should show "active (running)"**.

### Step 10: Test the System

Open your SurfSense instance in a browser and test with queries.

#### Test 1: English Query
1. Navigate to https://your-domain.com
2. Enter an English question about your documents
3. Expected: Response in ~5 seconds

#### Test 2: Latvian Query
1. Enter a Latvian question: "Kāds ir galvenais mērķis?"
2. Expected: Response in ~23 seconds (includes grammar check)

#### Test 3: Monitor Logs
```bash
# Watch backend logs in real-time
journalctl -u surfsense -f

# Watch Ollama logs
journalctl -u ollama -f
```

**Look for**:
- "Context window=131072" (not 1024000 or 4096)
- No truncation warnings
- Successful response generation
- No timeout errors

## Troubleshooting

### Issue: Ollama service won't start
```bash
# Check Ollama logs
journalctl -u ollama -n 50

# Try manual start
ollama serve

# Check port availability
sudo lsof -i :11434
```

### Issue: Model not found
```bash
# List installed models
ollama list

# Re-pull if missing
ollama pull mistral-nemo
ollama create mistral-nemo:128k -f /tmp/mistral-nemo-128k.modelfile
```

### Issue: Out of memory errors
```bash
# Check available RAM
free -h

# Check Ollama memory usage
ps aux | grep ollama

# Consider reducing concurrent models or using smaller quantizations
```

### Issue: Context still truncating to 4K
```bash
# Verify model configuration
ollama show mistral-nemo:128k --modelfile | grep num_ctx

# Should show: PARAMETER num_ctx 131072

# If not, recreate the model:
ollama rm mistral-nemo:128k
ollama create mistral-nemo:128k -f /tmp/mistral-nemo-128k.modelfile
```

### Issue: Backend not connecting to Ollama
```bash
# Test Ollama from backend server
curl http://localhost:11434/api/tags

# Check firewall
sudo ufw status

# Verify OLLAMA_BASE_URL in .env
grep OLLAMA /opt/SurfSense/surfsense_backend/.env
```

### Issue: Queries still hitting Gemini API instead of local models
```bash
# Check backend configuration
cat /opt/SurfSense/surfsense_backend/app/config/global_llm_config.yaml

# Verify model_name is "mistral-nemo:128k"
grep "model_name.*mistral" /opt/SurfSense/surfsense_backend/app/config/global_llm_config.yaml

# Restart backend
sudo systemctl restart surfsense
```

## Performance Tuning

### For 24GB RAM Systems
If you have less than 32GB RAM, use smaller models:

```bash
# Use smaller TildeOpen quantization
ollama pull tildeopen:30b-q4_k_m  # Instead of q5_k_m

# Or skip grammar checking by disabling in config
```

### For Faster Inference
```bash
# Use GPU acceleration (if available)
# Ollama automatically detects and uses CUDA/ROCm GPUs

# Check GPU usage
nvidia-smi  # For NVIDIA GPUs
```

### For Production Deployment
```bash
# Set Ollama to use specific GPU
CUDA_VISIBLE_DEVICES=0 ollama serve

# Limit concurrent requests in SurfSense config
# Edit systemd service file to set worker limits
```

## Maintenance

### Updating Models
```bash
# Check for model updates
ollama list

# Update a specific model
ollama pull mistral-nemo:latest

# Recreate optimized version
ollama create mistral-nemo:128k -f /tmp/mistral-nemo-128k.modelfile
```

### Cleaning Up Old Models
```bash
# Remove old model versions
ollama rm mistral-nemo:latest  # Keep only :128k version

# Free up disk space
ollama prune  # Removes unused layers
```

### Monitoring
```bash
# Monitor RAM usage
watch -n 1 free -h

# Monitor Ollama
journalctl -u ollama -f

# Monitor backend
journalctl -u surfsense -f
```

## Security Considerations

1. **API Key Security**: Never commit `global_llm_config.yaml` with real API keys to git
2. **Firewall**: Ensure Ollama port 11434 is not exposed to internet
3. **Updates**: Keep Ollama and models updated for security patches
4. **Logs**: Regularly rotate and clean logs to prevent disk filling

## Backup Recommendations

```bash
# Backup Ollama models directory
tar -czf ollama-models-backup.tar.gz /usr/share/ollama/.ollama/models/

# Backup SurfSense configuration
tar -czf surfsense-config-backup.tar.gz /opt/SurfSense/surfsense_backend/app/config/

# Store backups securely offsite
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/okapteinis/SurfSense/issues
- Documentation: See MIGRATION_LOCAL_LLM.md
- Email: ojars@kapteinis.lv

## License

This installation guide is part of the SurfSense project.

---

**Installation Complete!** You now have a fully local European AI stack with 95% cost reduction and improved performance.
