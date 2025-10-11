#!/usr/bin/env python3
"""Test script for local STT functionality."""

import asyncio
import requests
import tempfile
import wave
import numpy as np

def create_test_audio():
    """Create a simple test audio file."""
    # Generate 3 seconds of sine wave at 440Hz (A note)
    sample_rate = 16000
    duration = 3
    frequency = 440
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * frequency * t) * 0.3
    
    # Convert to 16-bit PCM
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # Save as WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        with wave.open(f.name, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        return f.name

def test_stt_api():
    """Test the STT API endpoint."""
    base_url = "http://localhost:8000/api/v1/stt"
    
    # Test 1: Get available models
    print("Testing /models endpoint...")
    response = requests.get(f"{base_url}/models")
    if response.status_code == 200:
        print("✓ Models endpoint working")
        print(f"Current model: {response.json()['current_model']}")
    else:
        print(f"✗ Models endpoint failed: {response.status_code}")
        return
    
    # Test 2: Create test audio and transcribe
    print("\nTesting transcription...")
    audio_file = create_test_audio()
    
    try:
        with open(audio_file, 'rb') as f:
            files = {'audio': ('test.wav', f, 'audio/wav')}
            response = requests.post(f"{base_url}/transcribe", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✓ Transcription successful")
            print(f"Text: {result['transcription']}")
            print(f"Language: {result['metadata']['detected_language']}")
            print(f"Duration: {result['metadata']['duration_seconds']:.2f}s")
        else:
            print(f"✗ Transcription failed: {response.status_code}")
            print(response.text)
    
    finally:
        import os
        os.unlink(audio_file)

if __name__ == "__main__":
    print("SurfSense STT Test")
    print("==================")
    print("Make sure the backend is running on localhost:8000")
    print()
    
    try:
        test_stt_api()
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to backend. Is it running?")
    except Exception as e:
        print(f"✗ Test failed: {e}")