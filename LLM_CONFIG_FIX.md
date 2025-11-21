# LLM Configuration Fix: Correct Model Priority Order

## Problem
The global LLM configuration had incorrect model priority:
- **Before:** Mistral Small (primary) → TildeOpen (grammar) → Gemini Flash (fallback)
- **Expected:** Gemini Flash (primary) → TildeOpen (grammar) → Mistral NeMo (fallback)

Additionally, the Gemini API key was hardcoded in the YAML file, which is a security risk.

## Root Cause
The `global_llm_config.yaml` file had the models configured in the wrong order with ID assignments that didn't match the intended architecture. The API key was also exposed in the configuration file instead of being securely stored in environment variables.

## Solution Applied

### 1. Reordered LLM Models
Updated model priority to match the intended three-tier architecture:

| ID | Model | Role | Provider |
|---|---|---|---|
| -1 | Gemini 2.0 Flash | **PRIMARY** - Main response generation | Google API |
| -2 | TildeOpen 30B | **GRAMMAR** - Latvian grammar checking | Ollama (local) |
| -3 | Mistral NeMo 12B | **FALLBACK** - Backup when Gemini unavailable | Ollama (local) |

### 2. Secured API Keys
- Moved Gemini API key from YAML to `.env` file
- Implemented environment variable expansion in config loader
- Updated YAML to use `${GEMINI_API_KEY}` placeholder

### 3. Added Environment Variable Expansion
Created `expand_env_vars()` function in `app/config/__init__.py` to:
- Recursively process configuration dictionaries
- Replace `${VAR_NAME}` patterns with environment variable values
- Maintain backward compatibility (keeps original if var not found)

## Changes Made

### Files Modified (Tracked in Git):
1. **`surfsense_backend/app/config/__init__.py`**
   - Added `import re` for regex support
   - Added `expand_env_vars()` function
   - Updated `load_global_llm_configs()` to expand environment variables

2. **`surfsense_backend/app/config/global_llm_config.example.yaml`**
   - Reordered models: Gemini (primary) → TildeOpen (grammar) → Mistral (fallback)
   - Changed API key to use `${GEMINI_API_KEY}` placeholder
   - Updated comments to reflect correct architecture

3. **`surfsense_backend/app/config/global_llm_config.yaml.template`**
   - Synchronized with example file

### Files Modified (NOT Tracked - Local Configuration):
4. **`.env`** - Added `GEMINI_API_KEY=<actual-key>`
5. **`global_llm_config.yaml`** - Updated with correct order and env var reference

## Security Improvements
- ✅ API keys no longer hardcoded in YAML files
- ✅ Secrets stored securely in `.env` file (not tracked by git)
- ✅ Configuration files can be safely committed to version control
- ✅ Environment variable expansion allows flexible configuration

## Impact
- ✅ Gemini Flash now used as primary model for faster, cost-effective responses
- ✅ TildeOpen correctly positioned for Latvian grammar checking
- ✅ Mistral NeMo serves as reliable fallback for offline/rate-limited scenarios
- ✅ API keys secured and no longer exposed in configuration files
