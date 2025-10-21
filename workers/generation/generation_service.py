"""
Generation Service - Handles AI-powered audio stem generation
Supports multiple models: MusicGen (Meta AI) and Stable Audio Open
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio

import numpy as np
import soundfile as sf
import librosa

logger = logging.getLogger(__name__)


class GenerationService:
    """Service for AI-powered audio generation"""
    
    def __init__(self):
        self.sample_rate = 44100
        self.use_gpu = os.getenv("USE_GPU", "false").lower() == "true"
        
        # Model availability flags
        self.has_stable_audio = False
        self.has_musicgen = False
        self.has_bark = False
        
        # Initialize AI models (real models required - no mock mode)
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize AI models (Stable Audio Open, MusicGen)"""
        try:
            import torch
            
            device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing models on device: {device}")
            
            # Try to load Stable Audio Open
            try:
                # Note: Stable Audio Open requires specific setup
                # This is a placeholder for actual model loading
                logger.info("Loading Stable Audio Open model...")
                # from stable_audio_tools import get_pretrained_model
                # self.stable_audio_model = get_pretrained_model("stabilityai/stable-audio-open-1.0")
                # self.stable_audio_model.to(device)
                self.has_stable_audio = False  # Set to True when model loaded
                logger.info("Stable Audio Open: Not loaded (placeholder)")
            except Exception as e:
                logger.warning(f"Failed to load Stable Audio Open: {e}")
            
            # Try to load Bark
            try:
                logger.info("Loading Bark model...")
                from bark import preload_models
                preload_models()
                self.has_bark = True
                logger.info("Bark loaded successfully")
            except ImportError as e:
                logger.warning(f"Bark not installed: {e}")
                logger.warning("Bark unavailable. Install with: pip install git+https://github.com/suno-ai/bark.git")
                self.has_bark = False
            except Exception as e:
                logger.warning(f"Failed to load Bark: {e}")
                self.has_bark = False
            
            # Check if we have at least one model available
            if not self.has_stable_audio and not self.has_musicgen and not self.has_bark:
                logger.warning("No AI models available! Generation requests will use fallback methods.")
                logger.warning("Install audiocraft for MusicGen: pip install audiocraft==1.3.0")
                logger.warning("Install Bark: pip install git+https://github.com/suno-ai/bark.git")
                
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
            
            # Use available AI models (real generation only)
            if self.has_bark:
                # Use Bark for generation
                audio = await self._generate_with_bark(stem_type, parameters)
            elif self.has_musicgen:
                # Use MusicGen for generation
                audio = await self._generate_with_musicgen(stem_type, parameters)
            elif self.has_stable_audio:
                # Use Stable Audio Open for generation
                audio = await self._generate_with_stable_audio(stem_type, parameters)
            else:
                raise RuntimeError("No AI generation models available. Please install MusicGen (audiocraft) or Stable Audio.")
            
            # Save audio to file
            sf.write(output_path, audio, self.sample_rate)
            logger.info(f"Saved generated audio: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating stem {stem_type}: {str(e)}", exc_info=True)
            return None

    async def _generate_with_bark(
        self,
        stem_type: str,
        parameters: Dict[str, Any]
    ) -> np.ndarray:
        """
        Generate audio using Suno's Bark model
        """
        logger.info(f"Generating with Bark: {stem_type}")
        
        try:
            from bark import generate_audio, SAMPLE_RATE
            # Build prompt from parameters
            prompt = self._build_prompt(stem_type, parameters)
            
            logger.info(f"Bark prompt: {prompt}")
            
            # Generate audio
            # Note: This is run in a thread pool to avoid blocking
            audio = await asyncio.to_thread(
                generate_audio,
                prompt
            )
            
            # Resample if necessary
            if SAMPLE_RATE != self.sample_rate:
                audio = librosa.resample(audio, orig_sr=SAMPLE_RATE, target_sr=self.sample_rate)

            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Bark generation failed: {e}")
            raise RuntimeError(f"Bark generation failed: {e}")
    
    async def _generate_with_musicgen(
        self,
        stem_type: str,
        parameters: Dict[str, Any]
    ) -> np.ndarray:
        """
        Generate audio using Meta's MusicGen model
        """
        logger.info(f"Generating with MusicGen: {stem_type}")
        
        try:
            # Build prompt from parameters
            prompt = self._build_prompt(stem_type, parameters)
            duration = parameters.get("duration_seconds", 10.0)
            
            logger.info(f"MusicGen prompt: {prompt}, duration: {duration}s")
            
            # Generate audio
            # Note: This is run in a thread pool to avoid blocking
            audio = await asyncio.to_thread(
                self._musicgen_generate,
                prompt,
                duration
            )
            
            # Convert to stereo if mono
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
        """Synchronous MusicGen generation (runs in thread)"""
        self.musicgen_model.set_generation_params(duration=duration)
        wav = self.musicgen_model.generate([prompt], progress=False)
        return wav[0].cpu().numpy()
    
    async def _generate_with_stable_audio(
        self,
        stem_type: str,
        parameters: Dict[str, Any]
    ) -> np.ndarray:
        """
        Generate audio using Stability AI's Stable Audio Open
        (Placeholder - requires actual implementation)
        """
        raise NotImplementedError("Stable Audio Open integration not yet implemented")
    
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
