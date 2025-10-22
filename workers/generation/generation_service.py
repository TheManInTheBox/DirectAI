"""
Generation Service - Handles AI-powered audio stem generation
Uses MusicGen (Meta AI) for music generation and training
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncio

import numpy as np
import soundfile as sf
import librosa

logger = logging.getLogger(__name__)


class GenerationService:
    """Service for AI-powered audio generation using MusicGen"""
    
    def __init__(self):
        self.sample_rate = 32000  # MusicGen uses 32kHz
        self.use_gpu = os.getenv("USE_GPU", "false").lower() == "true"
        
        # Model availability flags
        self.has_musicgen = False
        self.musicgen_model = None
        self.musicgen_processor = None
        
        # Initialize MusicGen model
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize MusicGen model"""
        try:
            import torch
            from transformers import AutoProcessor, MusicgenForConditionalGeneration
            
            device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing MusicGen on device: {device}")
            
            # Load MusicGen model
            try:
                logger.info("Loading MusicGen model (facebook/musicgen-small)...")
                self.musicgen_processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
                self.musicgen_model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
                self.musicgen_model.to(device)
                self.has_musicgen = True
                logger.info("MusicGen loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load MusicGen: {e}")
                logger.warning("Install audiocraft for MusicGen: pip install transformers accelerate audiocraft")
                self.has_musicgen = False
                raise RuntimeError(f"MusicGen initialization failed: {e}")
                
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            raise RuntimeError(f"Model initialization failed: {e}")
    
    async def generate_stem(
        self,
        stem_type: str,
        parameters: Dict[str, Any],
        output_dir: Path
    ) -> Optional[Path]:
        """
        Generate an audio stem using AI models
        
        Args:
            stem_type: Type of stem (vocals, drums, bass, guitar, etc.)
            parameters: Generation parameters (BPM, style, chords, prompt, etc.)
            output_dir: Directory to save generated audio
            
        Returns:
            Path to generated audio file (WAV format)
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{stem_type}.wav"
            
            # Use MusicGen for generation
            if self.has_musicgen:
                audio = await self._generate_with_musicgen(stem_type, parameters)
            else:
                raise RuntimeError("MusicGen not available. Generation worker not properly initialized.")
            
            # Resample to 44.1kHz for compatibility
            if audio.shape[0] > 0:
                audio_resampled = librosa.resample(
                    audio.T, 
                    orig_sr=self.sample_rate, 
                    target_sr=44100
                ).T
                sf.write(output_path, audio_resampled, 44100)
            else:
                sf.write(output_path, audio, self.sample_rate)
            
            logger.info(f"Saved generated audio: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating stem {stem_type}: {str(e)}", exc_info=True)
            return None
    
    async def _generate_with_musicgen(
        self,
        stem_type: str,
        parameters: Dict[str, Any]
    ) -> np.ndarray:
        """
        Generate audio using Meta's MusicGen model
        
        Parameters can include:
        - prompt: Text description of the music
        - duration_seconds: Length of generation
        - bpm: Target BPM
        - key: Target musical key
        - style: Musical style description
        """
        logger.info(f"Generating with MusicGen: {stem_type}")
        
        try:
            # Build prompt from parameters
            prompt = self._build_prompt(stem_type, parameters)
            duration = parameters.get("duration_seconds", 10.0)
            
            logger.info(f"MusicGen prompt: {prompt}, duration: {duration}s")
            
            # Generate audio (run in thread pool to avoid blocking)
            audio = await asyncio.to_thread(
                self._musicgen_generate,
                prompt,
                duration
            )
            
            # Convert to stereo if needed
            if audio.ndim == 1:
                audio = np.column_stack([audio, audio])
            elif audio.shape[0] == 1:  # (1, samples)
                audio = audio.T
                audio = np.column_stack([audio, audio])
            elif audio.shape[0] == 2:  # (2, samples)
                audio = audio.T
            
            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"MusicGen generation failed: {e}")
            raise RuntimeError(f"MusicGen generation failed: {e}")
    
    def _musicgen_generate(self, prompt: str, duration: float) -> np.ndarray:
        """
        Synchronous MusicGen generation (runs in thread)
        Uses HuggingFace transformers API
        """
        import torch
        
        # Process the prompt
        inputs = self.musicgen_processor(
            text=[prompt],
            padding=True,
            return_tensors="pt",
        )
        
        # Calculate max_new_tokens based on duration
        # MusicGen generates at 50 Hz (50 tokens per second)
        max_new_tokens = int(duration * 50)
        
        # Move inputs to same device as model
        device = next(self.musicgen_model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Generate
        with torch.no_grad():
            audio_values = self.musicgen_model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                guidance_scale=3.0
            )
        
        # Convert to numpy and squeeze
        audio = audio_values.cpu().squeeze().numpy()
        
        return audio
    
    def _build_prompt(self, stem_type: str, parameters: Dict[str, Any]) -> str:
        """
        Build a text prompt for AI generation based on parameters
        """
        # Start with user prompt if provided
        prompt = parameters.get("prompt", "")
        
        if not prompt:
            # Build prompt from stem type and parameters
            style = parameters.get("style", "")
            target_bpm = parameters.get("target_bpm")
            
            # Base prompt for stem type
            stem_prompts = {
                "drums": "drum track with kick, snare, and hi-hat",
                "bass": "bass guitar line",
                "guitar": "electric guitar",
                "vocals": "vocal melody",
                "piano": "piano melody",
                "synth": "synthesizer pad"
            }
            
            prompt = stem_prompts.get(stem_type, f"{stem_type} track")
            
            # Add style
            if style:
                prompt = f"{style} {prompt}"
            
            # Add tempo
            if target_bpm:
                tempo_desc = "slow" if target_bpm < 90 else "fast" if target_bpm > 140 else "medium tempo"
                prompt = f"{tempo_desc} {prompt}"
        
        return prompt
