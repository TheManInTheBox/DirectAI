"""
Generation Service - Handles AI-powered audio generation with trained models
Uses MusicGen (Meta AI) for music generation with LoRA fine-tuning support
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
import tempfile
import zipfile

import numpy as np
import soundfile as sf
import librosa

logger = logging.getLogger(__name__)


class GenerationService:
    """Service for AI-powered audio generation using MusicGen with trained model support"""
    
    def __init__(self, storage_service=None):
        self.sample_rate = 32000  # MusicGen uses 32kHz
        self.use_gpu = os.getenv("USE_GPU", "false").lower() == "true"
        self.storage_service = storage_service
        
        # Model availability flags
        self.has_musicgen = False
        self.base_model = None
        self.processor = None
        
        # Loaded trained models cache
        self.loaded_models = {}  # {model_id: (model, timestamp)}
        
        # Initialize MusicGen base model
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize MusicGen base model"""
        try:
            import torch
            from transformers import AutoProcessor, MusicgenForConditionalGeneration
            
            device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing MusicGen on device: {device}")
            
            # Load MusicGen base model
            try:
                logger.info("Loading MusicGen base model (facebook/musicgen-melody-large)...")
                self.processor = AutoProcessor.from_pretrained("facebook/musicgen-melody-large")
                self.base_model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-melody-large")
                self.base_model.to(device)
                self.has_musicgen = True
                logger.info("MusicGen base model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load MusicGen: {e}")
                logger.warning("Install audiocraft for MusicGen: pip install transformers accelerate audiocraft")
                self.has_musicgen = False
                raise RuntimeError(f"MusicGen initialization failed: {e}")
                
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            raise RuntimeError(f"Model initialization failed: {e}")
    
    async def generate_track(
        self,
        parameters: Dict[str, Any],
        output_dir: Path
    ) -> Optional[Path]:
        """
        Generate a single complete audio track using trained model or base MusicGen
        
        Args:
            parameters: Generation parameters including:
                - trained_model_id: Optional UUID of trained model to use
                - key: Musical key (e.g., "C", "D#")
                - scale: Scale (e.g., "major", "minor")
                - time_signature: Time signature (e.g., "4/4", "3/4")
                - bpm: Target BPM
                - bars: Number of bars
                - style: Style description
                - prompt: Optional text prompt override
            output_dir: Directory to save generated audio
            
        Returns:
            Path to generated audio file (WAV format) - single complete track
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "generated_track.wav"
            
            trained_model_id = parameters.get("trained_model_id")
            
            if trained_model_id:
                # Use trained model
                logger.info(f"Generating with trained model: {trained_model_id}")
                model = await self._load_trained_model(trained_model_id)
                audio = await self._generate_with_trained_model(model, parameters)
            elif self.has_musicgen:
                # Use base MusicGen
                logger.info("Generating with base MusicGen model")
                audio = await self._generate_with_base_model(parameters)
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
            
            logger.info(f"Saved generated track: {output_path}")
            
            logger.info(f"Saved generated track: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating track: {str(e)}", exc_info=True)
            return None
    
    async def _load_trained_model(self, model_id: str):
        """Load a trained model (LoRA checkpoint) from blob storage"""
        import torch
        from peft import PeftModel
        
        # Check cache
        if model_id in self.loaded_models:
            logger.info(f"Using cached trained model: {model_id}")
            return self.loaded_models[model_id]
        
        logger.info(f"Loading trained model {model_id} from blob storage...")
        
        # Download checkpoint from blob storage
        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint_path = Path(temp_dir) / "checkpoint.zip"
            checkpoint_dir = Path(temp_dir) / "checkpoint"
            
            # Download checkpoint
            blob_path = f"models/{model_id}/checkpoint.zip"
            await self.storage_service.download_blob(blob_path, str(checkpoint_path))
            
            # Extract checkpoint
            with zipfile.ZipFile(checkpoint_path, 'r') as zip_ref:
                zip_ref.extractall(checkpoint_dir)
            
            # Load LoRA adapters onto base model
            logger.info("Applying LoRA adapters to base model...")
            model = PeftModel.from_pretrained(
                self.base_model,
                checkpoint_dir,
                is_trainable=False
            )
            model.eval()
            
            # Cache the model
            self.loaded_models[model_id] = model
            logger.info(f"Trained model {model_id} loaded successfully")
            
            return model
    
    async def _generate_with_trained_model(
        self,
        model,
        parameters: Dict[str, Any]
    ) -> np.ndarray:
        """Generate audio using a trained LoRA model"""
        logger.info("Generating with trained LoRA model")
        
        try:
            # Build prompt from musical parameters
            prompt = self._build_prompt_from_parameters(parameters)
            duration = self._calculate_duration(parameters)
            
            logger.info(f"Generation prompt: {prompt}, duration: {duration}s")
            
            # Generate audio (run in thread pool to avoid blocking)
            audio = await asyncio.to_thread(
                self._run_generation,
                model,
                prompt,
                duration
            )
            
            # Convert to stereo
            audio = self._to_stereo(audio)
            
            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Trained model generation failed: {e}")
            raise RuntimeError(f"Trained model generation failed: {e}")
    
    async def _generate_with_base_model(
        self,
        parameters: Dict[str, Any]
    ) -> np.ndarray:
        """Generate audio using base MusicGen model (no training)"""
        logger.info("Generating with base MusicGen model")
        
        try:
            # Build prompt
            prompt = self._build_prompt_from_parameters(parameters)
            duration = self._calculate_duration(parameters)
            
            logger.info(f"Base model prompt: {prompt}, duration: {duration}s")
            
            # Generate audio
            audio = await asyncio.to_thread(
                self._run_generation,
                self.base_model,
                prompt,
                duration
            )
            
            # Convert to stereo
            audio = self._to_stereo(audio)
            
            return audio.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Base model generation failed: {e}")
            raise RuntimeError(f"Base model generation failed: {e}")
    
    def _run_generation(self, model, prompt: str, duration: float) -> np.ndarray:
        """
        Synchronous generation (runs in thread)
        Works with both base model and LoRA models
        """
        import torch
        
        # Process the prompt
        inputs = self.processor(
            text=[prompt],
            padding=True,
            return_tensors="pt",
        )
        
        # Calculate max_new_tokens based on duration
        # MusicGen generates at 50 Hz (50 tokens per second)
        max_new_tokens = int(duration * 50)
        
        # Move inputs to same device as model
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Generate
        with torch.no_grad():
            audio_values = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                guidance_scale=3.0
            )
        
        # Convert to numpy and squeeze
        audio = audio_values.cpu().squeeze().numpy()
        
        return audio
    
    def _build_prompt_from_parameters(self, parameters: Dict[str, Any]) -> str:
        """Build a text prompt from musical parameters"""
        
        # Use custom prompt if provided
        if parameters.get("prompt"):
            return parameters["prompt"]
        
        # Build prompt from musical parameters
        parts = []
        
        # Style
        style = parameters.get("style", "")
        if style:
            parts.append(style)
        
        # Tempo/BPM
        bpm = parameters.get("bpm") or parameters.get("target_bpm")
        if bpm:
            if bpm < 80:
                parts.append("slow tempo")
            elif bpm < 100:
                parts.append("moderate tempo")
            elif bpm < 130:
                parts.append("upbeat tempo")
            else:
                parts.append("fast tempo")
        
        # Key and scale
        key = parameters.get("key")
        scale = parameters.get("scale")
        if key:
            if scale:
                parts.append(f"in {key} {scale}")
            else:
                parts.append(f"in {key}")
        
        # Time signature
        time_sig = parameters.get("time_signature")
        if time_sig:
            if time_sig == "3/4":
                parts.append("waltz time")
            elif time_sig == "6/8":
                parts.append("six-eight time")
            elif time_sig in ["5/4", "7/8"]:
                parts.append("complex rhythm")
        
        # Base description
        if not parts:
            parts.append("instrumental music track")
        else:
            parts.append("music")
        
        return " ".join(parts)
    
    def _calculate_duration(self, parameters: Dict[str, Any]) -> float:
        """Calculate duration from bars and BPM, or use duration_seconds"""
        
        # Direct duration parameter
        if "duration_seconds" in parameters:
            return float(parameters["duration_seconds"])
        
        # Calculate from bars and BPM
        bars = parameters.get("bars")
        bpm = parameters.get("bpm") or parameters.get("target_bpm")
        time_sig = parameters.get("time_signature", "4/4")
        
        if bars and bpm:
            # Parse time signature
            numerator = int(time_sig.split('/')[0])
            
            # Calculate duration
            # bars * (beats_per_bar / BPM) * 60 seconds
            beats_per_bar = numerator
            duration = bars * (beats_per_bar / bpm) * 60
            
            logger.info(f"Calculated duration: {bars} bars at {bpm} BPM in {time_sig} = {duration}s")
            return duration
        
        # Default duration
        return 10.0
    
    def _to_stereo(self, audio: np.ndarray) -> np.ndarray:
        """Convert audio to stereo format"""
        if audio.ndim == 1:
            # Mono to stereo
            audio = np.column_stack([audio, audio])
        elif audio.shape[0] == 1:  # (1, samples)
            audio = audio.T
            audio = np.column_stack([audio, audio])
        elif audio.shape[0] == 2:  # (2, samples)
            audio = audio.T
        
        return audio
    
    # Legacy method for backward compatibility (generates single track, not stems)
    async def generate_stem(
        self,
        stem_type: str,
        parameters: Dict[str, Any],
        output_dir: Path
    ) -> Optional[Path]:
        """
        Legacy method - now generates a complete track (not individual stems)
        Maintained for backward compatibility with existing code
        """
        logger.warning(f"generate_stem() is deprecated - generating complete track instead of {stem_type} stem")
        return await self.generate_track(parameters, output_dir)
        return prompt
