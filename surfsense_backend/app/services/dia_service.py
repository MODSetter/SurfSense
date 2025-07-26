"""
Dia TTS Service for Local Podcast Generation

This service provides integration with the Dia text-to-speech model for fully local podcast generation.
Dia is a 1.6B parameter text-to-speech model that can generate realistic dialogue from transcripts.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import torch

logger = logging.getLogger(__name__)


class DiaServiceError(Exception):
    """Base exception for Dia service errors."""
    pass


class GPUNotAvailableError(DiaServiceError):
    """Raised when GPU is required but not available."""
    pass


class DiaService:
    """Service for managing Dia text-to-speech operations."""
    
    def __init__(self):
        self._model = None
        self._device = None
        self._is_initialized = False
        
    def check_gpu_availability(self) -> tuple[bool, str]:
        """
        Check if a GPU is available for Dia TTS generation.
        
        Returns:
            tuple[bool, str]: (is_available, device_info)
        """
        try:
            import torch
            
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0)
                total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB
                
                if total_memory >= 4.0:  # Dia needs at least 4GB VRAM
                    return True, f"CUDA GPU available: {gpu_name} ({total_memory:.1f}GB VRAM, {gpu_count} device(s))"
                else:
                    return False, f"GPU has insufficient VRAM: {total_memory:.1f}GB (need 4GB+)"
            
            # Check for Apple Silicon MPS
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return True, "Apple Silicon MPS available"
            
            return False, "No GPU available (CUDA or MPS)"
            
        except ImportError:
            return False, "PyTorch not installed"
        except Exception as e:
            return False, f"Error checking GPU availability: {e}"

    def _check_dia_dependencies(self) -> bool:
        """
        Check if Dia dependencies are available.
        
        Returns:
            bool: True if all dependencies are available
        """
        try:
            import torch
            # Try to import dia - this will fail if not installed
            import dia
            return True
        except ImportError:
            return False
    
    def is_dia_available(self) -> tuple[bool, str]:
        """
        Check if Dia should be used for TTS generation.
        
        Returns:
            tuple[bool, str]: (is_available, message)
        """
        from app.config import config
        
        # Check if Dia is enabled in configuration
        if not getattr(config, 'ENABLE_DIA_TTS', True):
            return False, "Dia TTS is disabled in configuration"
        
        # Check if dependencies are available
        if not self._check_dia_dependencies():
            return False, "Dia dependencies not installed. Install with: pip install -e .[local-tts]"
        
        # Check GPU availability
        gpu_available, gpu_message = self.check_gpu_availability()
        
        if not gpu_available:
            return False, f"Dia requires GPU but none available: {gpu_message}"
        
        return True, f"Dia TTS ready with {gpu_message}"
    
    def _get_optimal_device(self) -> torch.device:
        """Get the optimal device for Dia inference."""
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        else:
            # This should not happen if GPU check passed
            raise GPUNotAvailableError("No GPU available for Dia")
    
    def _get_optimal_dtype(self, device: torch.device) -> str:
        """Get optimal dtype based on device."""
        dtype_map = {
            "cpu": "float32",
            "mps": "float32",  # Apple M series – better with float32
            "cuda": "float16",  # NVIDIA – better with float16
        }
        return dtype_map.get(device.type, "float16")
    
    def initialize_model(self) -> None:
        """Initialize the Dia model."""
        if self._is_initialized:
            return
            
        available, message = self.is_dia_available()
        if not available:
            raise DiaServiceError(message)
        
        try:
            from dia.model import Dia
            
            self._device = self._get_optimal_device()
            compute_dtype = self._get_optimal_dtype(self._device)
            
            logger.info(f"Loading Dia model on {self._device} with dtype {compute_dtype}")
            
            self._model = Dia.from_pretrained(
                "nari-labs/Dia-1.6B-0626",
                compute_dtype=compute_dtype,
                device=self._device
            )
            
            self._is_initialized = True
            logger.info("Dia model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Dia model: {e}")
            raise DiaServiceError(f"Failed to initialize Dia model: {e}")
    
    def generate_audio(
        self,
        text: str,
        output_path: str,
        audio_prompt: Optional[str] = None,
        max_tokens: int = 3072,
        cfg_scale: float = 3.0,
        temperature: float = 1.8,
        top_p: float = 0.90,
        cfg_filter_top_k: int = 45,
        seed: Optional[int] = None,
        use_torch_compile: bool = False
    ) -> str:
        """
        Generate audio from text using Dia.
        
        Args:
            text: Text to convert to speech (should use [S1] and [S2] speaker tags)
            output_path: Path where the generated audio will be saved
            audio_prompt: Optional path to audio file for voice cloning
            max_tokens: Maximum number of audio tokens to generate
            cfg_scale: Classifier-Free Guidance scale
            temperature: Sampling temperature
            top_p: Nucleus sampling probability
            cfg_filter_top_k: Top-k filtering for CFG
            seed: Random seed for reproducibility
            use_torch_compile: Whether to use torch.compile for faster inference
            
        Returns:
            str: Path to the generated audio file
            
        Raises:
            DiaServiceError: If generation fails
        """
        if not self._is_initialized:
            self.initialize_model()
        
        try:
            # Set seed if provided
            if seed is not None:
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed(seed)
                    torch.cuda.manual_seed_all(seed)
            
            # Ensure text has proper speaker tags
            if not ("[S1]" in text or "[S2]" in text):
                # Auto-format simple text with speaker tags
                sentences = text.split(". ")
                formatted_text = ""
                for i, sentence in enumerate(sentences):
                    if sentence.strip():
                        speaker = "[S1]" if i % 2 == 0 else "[S2]"
                        formatted_text += f"{speaker} {sentence.strip()}. "
                text = formatted_text.strip()
            
            logger.info(f"Generating audio with Dia: {len(text)} characters")
            
            # Generate audio
            with torch.inference_mode():
                output_audio = self._model.generate(
                    text,
                    max_tokens=max_tokens,
                    cfg_scale=cfg_scale,
                    temperature=temperature,
                    top_p=top_p,
                    cfg_filter_top_k=cfg_filter_top_k,
                    use_torch_compile=use_torch_compile,
                    audio_prompt=audio_prompt,
                    verbose=False
                )
            
            # Save audio
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self._model.save_audio(output_path, output_audio)
            
            logger.info(f"Audio generated successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to generate audio with Dia: {e}")
            raise DiaServiceError(f"Failed to generate audio: {e}")
    
    def convert_podcast_transcript_to_dia_format(self, transcript_entries: list[dict]) -> str:
        """
        Convert SurfSense podcast transcript format to Dia format.
        
        Args:
            transcript_entries: List of transcript entries with speaker_id and dialog
            
        Returns:
            str: Formatted text for Dia
        """
        dia_text = ""
        
        for entry in transcript_entries:
            speaker_id = entry.get("speaker_id", 0)
            dialog = entry.get("dialog", "")
            
            # Map speaker IDs to Dia format
            # SurfSense uses 0, 1, 2... while Dia uses [S1], [S2]
            if speaker_id == 0:
                speaker_tag = "[S1]"
            elif speaker_id == 1:
                speaker_tag = "[S2]" 
            else:
                # For more than 2 speakers, alternate between S1 and S2
                speaker_tag = "[S1]" if speaker_id % 2 == 0 else "[S2]"
            
            # Clean up dialog text
            dialog = dialog.strip()
            if dialog and not dialog.endswith(('.', '!', '?')):
                dialog += "."
            
            dia_text += f"{speaker_tag} {dialog} "
        
        return dia_text.strip()
    
    def cleanup(self) -> None:
        """Clean up model resources."""
        if self._model is not None:
            del self._model
            self._model = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        self._is_initialized = False
        logger.info("Dia model resources cleaned up")


# Global instance
_dia_service = None


def get_dia_service() -> DiaService:
    """Get the global Dia service instance."""
    global _dia_service
    if _dia_service is None:
        _dia_service = DiaService()
    return _dia_service
