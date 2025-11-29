# Latvian Text-to-Speech Integration

## Overview

SurfSense now supports high-quality Latvian text-to-speech (TTS) for podcast generation using Coqui TTS (Mozilla TTS) with TildeOpen integration for text preprocessing.

## Features

### Latvian TTS
- **Automatic Language Detection**: Detects Latvian text and uses appropriate TTS engine
- **Text Preprocessing**: Uses TildeOpen LLM for grammar checking and text normalization
- **Number Conversion**: Converts numbers to Latvian words (e.g., "123" → "simts divdesmit trīs")
- **Date Normalization**: Converts dates to speech-friendly format
- **Abbreviation Expansion**: Expands common Latvian abbreviations
- **Fallback Support**: Falls back to default TTS if Latvian TTS is unavailable

### Supported Features

#### Text Preprocessing
1. **Grammar Checking** (via TildeOpen)
   - Automatic grammar correction
   - Language-specific prompts
   - Optional (can be disabled)

2. **Number Normalization**
   - Integers: 1-999 → Latvian words
   - Dates: YYYY-MM-DD → "gada <month> <day>"

3. **Abbreviation Expansion**
   - Common abbreviations (u.c., piem., t.i., etc.)
   - Units (kg, m, km, etc.)
   - Organizations (SIA, AS, IK, etc.)
   - Titles (Dr., prof., akad., etc.)

4. **Special Character Handling**
   - Symbols → words (& → "un", % → "procenti", etc.)
   - Currency symbols (€ → "eiro", $ → "dolāri")
   - Math operators (+ → "plus", = → "vienāds ar")

## Architecture

### Components

1. **LatvianTextPreprocessor** (`app/services/latvian_text_preprocessing.py`)
   - Text normalization
   - TildeOpen integration for grammar checking
   - Number and date conversion
   - Abbreviation expansion

2. **LatvianTTSService** (`app/services/latvian_tts_service.py`)
   - Coqui TTS integration
   - Audio generation
   - Podcast creation
   - Caching support

3. **Podcast Generation** (`app/agents/podcaster/nodes.py`)
   - Automatic language detection
   - Latvian TTS integration
   - Fallback to default TTS

### Integration with TildeOpen

TildeOpen (running via Ollama) is used for grammar checking:
- **Endpoint**: `http://localhost:11434/api/generate`
- **Model**: `tildeopen`
- **Language**: Latvian (lv)
- **Timeout**: 10 seconds

## Installation

### Prerequisites

1. **Coqui TTS**
```bash
pip install TTS torch torchaudio pydub soundfile
```

2. **TildeOpen** (via Ollama)
```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull TildeOpen model
ollama pull tildeopen

# Verify installation
ollama list | grep tildeopen
```

3. **System Dependencies**
```bash
# FFmpeg for audio processing
apt-get install ffmpeg

# Verify installation
ffmpeg -version
```

### Model Selection

The Latvian TTS service will automatically select the best available model:

1. **Latvian-specific model** (preferred)
   - Searches for models with "lv" in the name
   - Example: `tts_models/lv/XXXXX/vits`

2. **Multilingual model** (fallback)
   - `tts_models/multilingual/multi-dataset/your_tts`
   - `tts_models/multilingual/multi-dataset/xtts_v2`

3. **Custom model** (advanced)
   - Train your own model using Common Voice Latvian dataset
   - https://commonvoice.mozilla.org/lv/datasets

## Usage

### Automatic Podcast Generation

The system automatically detects Latvian text during podcast generation:

```python
# In podcast generation, language is detected automatically
# If Latvian is detected, LatvianTTSService is used
# Otherwise, default TTS (Kokoro or configured service) is used
```

### Manual Latvian TTS

```python
from app.services.latvian_tts_service import get_latvian_tts_service

# Get Latvian TTS service
tts_service = get_latvian_tts_service()

# Check if TTS is available
if tts_service.check_tts_available():
    # Generate audio from Latvian text
    audio_path = await tts_service.generate_audio(
        text="Labdien! Šis ir tests.",
        speaker=None,  # Optional speaker/voice
        preprocess=True,  # Enable text preprocessing
    )
    print(f"Audio saved to: {audio_path}")
else:
    print("Latvian TTS not available")
```

### Generate Multi-Section Podcast

```python
# Create podcast with multiple sections
sections = [
    {
        "text": "Laipni lūdzam SurfSense podkāstā!",
        "speaker": None,
        "pause_after": 1.0
    },
    {
        "text": "Šodien mēs runāsim par mākslīgo intelektu.",
        "speaker": None,
        "pause_after": 1.5
    },
    {
        "text": "Paldies par klausīšanos!",
        "speaker": None,
        "pause_after": 0.5
    }
]

output_path = await tts_service.generate_podcast(
    sections=sections,
    output_path="/path/to/podcast.mp3",
    pause_between_sections=1.0
)
```

### Text Preprocessing

```python
from app.services.latvian_text_preprocessing import get_latvian_text_preprocessor

# Get preprocessor
preprocessor = get_latvian_text_preprocessor()

# Preprocess text for TTS
text = "2025-11-22 Rīgā notika konference. Nr. 123 dalībnieki."
processed = await preprocessor.preprocess_for_tts(text, use_grammar_check=True)

# Result: "divi tūkstoši divdesmit piektais gada novembrī divdesmit otrais Rīgā notika konference. numurs simts divdesmit trīs dalībnieki."
```

## Configuration

### Environment Variables

No specific environment variables required. The service uses default configuration:
- **Ollama URL**: `http://localhost:11434`
- **Output Directory**: `/tmp/surfsense/tts/latvian`
- **Cache Directory**: `/tmp/surfsense/tts/cache`

### Customization

You can customize the service by modifying:

1. **Text Preprocessing Settings** (in `latvian_text_preprocessing.py`):
   - Add more abbreviations to `ABBREVIATIONS` dict
   - Modify number-to-words logic
   - Adjust special character replacements

2. **TTS Model** (in `latvian_tts_service.py`):
   - Specify custom model name
   - Adjust audio quality settings
   - Modify output format

## Language Detection

The system uses pattern-based language detection (`app/services/language_detector.py`):

```python
from app.services.language_detector import detect_language

text = "Labdien! Kā jums klājas?"
lang = detect_language(text)  # Returns: "lv"
```

Detection criteria:
- Minimum 3 words
- Minimum 10 characters
- Checks for Latvian-specific characters (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž)
- Checks for common Latvian keywords (un, ir, var, kas, etc.)

## Performance

### Text Preprocessing
- **Time**: ~0.1-1 seconds per text segment
- **TildeOpen**: 8-10 second timeout for grammar checking
- **Memory**: Minimal

### Audio Generation
- **Time**: ~0.1 seconds per character (hardware dependent)
- **Output Format**: WAV (24kHz sample rate)
- **File Size**: ~1-2MB per minute of audio

### Podcast Generation
- **Time**: Proportional to text length + audio concatenation
- **Output Format**: MP3 (128kbps, mono)
- **Concurrent Processing**: Segments generated in parallel

## Troubleshooting

### TildeOpen Not Responding

**Error**: Grammar check timed out

**Solution**:
```bash
# Check if Ollama is running
systemctl status ollama

# Restart Ollama
systemctl restart ollama

# Test TildeOpen
ollama run tildeopen "Pārbaudi šo tekstu."
```

### Coqui TTS Not Found

**Error**: "Coqui TTS not installed"

**Solution**:
```bash
# Install TTS and dependencies
pip install TTS torch torchaudio pydub soundfile

# Verify installation
python -c "from TTS.api import TTS; print('TTS installed successfully')"

# List available models
tts --list_models
```

### No Latvian Model Available

**Warning**: "No suitable TTS model found for Latvian"

**Solutions**:

1. **Use Multilingual Model**:
```bash
# Download YourTTS (multilingual)
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/your_tts')"
```

2. **Train Custom Model**:
   - Download Common Voice Latvian dataset
   - Follow Coqui TTS training guide
   - https://tts.readthedocs.io/en/latest/training_a_model.html

### Audio Quality Issues

**Issue**: Generated audio sounds robotic or unclear

**Solutions**:
- Enable text preprocessing: `preprocess=True`
- Use higher quality model
- Check TildeOpen grammar corrections
- Verify text normalization is working correctly

### Memory Issues

**Issue**: Out of memory during podcast generation

**Solutions**:
```python
# Process sections sequentially instead of in parallel
# Reduce concurrent segment generation
# Clear cache periodically
```

## Examples

### Number Conversion

```python
preprocessor.number_to_words(123)
# Output: "simts divdesmit trīs"

preprocessor.number_to_words(7)
# Output: "septiņi"
```

### Date Normalization

```python
text = "2025-11-22 notika konference"
processed = preprocessor.normalize_dates(text)
# Output: "divi tūkstoši divdesmit piektais gada novembrī divdesmit otrais notika konference"
```

### Abbreviation Expansion

```python
text = "SIA Acme, nr. 123, u.c. partneri"
processed = preprocessor.expand_abbreviations(text)
# Output: "sabiedrība ar ierobežotu atbildību Acme, numurs 123, un citi partneri"
```

## Future Enhancements

1. **Fine-tuned Latvian Model**: Train dedicated high-quality Latvian TTS model
2. **Voice Cloning**: Support for custom voice creation
3. **Prosody Control**: Adjust speed, pitch, and emotion
4. **Streaming TTS**: Real-time audio generation
5. **Batch Processing**: Process multiple texts efficiently
6. **Advanced Grammar**: Deeper TildeOpen integration for better text quality
7. **SSML Support**: Speech Synthesis Markup Language for fine control
8. **Caching**: Cache frequently used phrases for faster generation

## References

- **Coqui TTS**: https://github.com/coqui-ai/TTS
- **Common Voice**: https://commonvoice.mozilla.org/lv
- **TildeOpen**: https://huggingface.co/tilde
- **Ollama**: https://ollama.com/
