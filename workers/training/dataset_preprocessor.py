"""
MusicGen Training Dataset Preprocessor
Loads and preprocesses custom audio datasets with paired text prompts
Converts audio to mel spectrograms or latent embeddings for training
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json

import torch
import torchaudio
import numpy as np
from torch.utils.data import Dataset
from transformers import AutoProcessor, T5EncoderModel

logger = logging.getLogger(__name__)


class MusicGenDataset(Dataset):
    """
    PyTorch Dataset for MusicGen fine-tuning
    
    Loads audio files with paired text prompts and prepares them for training.
    Handles audio preprocessing (resampling, normalization) and text tokenization.
    """
    
    def __init__(
        self,
        audio_files: List[Path],
        prompts: List[str],
        target_sample_rate: int = 32000,
        max_duration_seconds: float = 30.0,
        processor: Optional[AutoProcessor] = None,
        cache_dir: Optional[Path] = None
    ):
        """
        Initialize the dataset
        
        Args:
            audio_files: List of paths to audio files (WAV/MP3)
            prompts: List of text prompts paired with audio files
            target_sample_rate: Target sample rate for MusicGen (32kHz)
            max_duration_seconds: Maximum audio duration in seconds
            processor: Hugging Face processor for tokenization
            cache_dir: Optional directory for caching preprocessed data
        """
        assert len(audio_files) == len(prompts), "Number of audio files must match number of prompts"
        
        self.audio_files = audio_files
        self.prompts = prompts
        self.target_sample_rate = target_sample_rate
        self.max_duration_seconds = max_duration_seconds
        self.max_length = int(max_duration_seconds * target_sample_rate)
        self.processor = processor
        self.cache_dir = cache_dir
        
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized MusicGenDataset with {len(audio_files)} samples")
        logger.info(f"Target sample rate: {target_sample_rate} Hz, Max duration: {max_duration_seconds}s")
    
    def __len__(self) -> int:
        return len(self.audio_files)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        Get a single training sample
        
        Returns:
            Dictionary containing:
                - input_ids: Tokenized text prompt
                - attention_mask: Attention mask for prompt
                - audio_codes: Audio codes from EnCodec
                - audio_values: Raw audio waveform (for validation)
        """
        audio_path = self.audio_files[idx]
        prompt = self.prompts[idx]
        
        # Check cache
        if self.cache_dir:
            cache_file = self.cache_dir / f"sample_{idx}.pt"
            if cache_file.exists():
                return torch.load(cache_file)
        
        # Load and preprocess audio
        audio_tensor = self._load_and_preprocess_audio(audio_path)
        
        # Tokenize text prompt
        text_inputs = self.processor(
            text=[prompt],
            padding="max_length",
            max_length=512,
            truncation=True,
            return_tensors="pt"
        )
        
        sample = {
            "input_ids": text_inputs["input_ids"].squeeze(0),
            "attention_mask": text_inputs["attention_mask"].squeeze(0),
            "audio_values": audio_tensor,
            "prompt": prompt  # Keep for debugging
        }
        
        # Cache the sample
        if self.cache_dir:
            cache_file = self.cache_dir / f"sample_{idx}.pt"
            torch.save(sample, cache_file)
        
        return sample
    
    def _load_and_preprocess_audio(self, audio_path: Path) -> torch.Tensor:
        """
        Load audio file and preprocess it
        
        Steps:
        1. Load audio (supports WAV, MP3, FLAC, etc.)
        2. Resample to target sample rate (32kHz for MusicGen)
        3. Convert to mono if stereo
        4. Normalize audio
        5. Pad or trim to max_length
        
        Returns:
            Preprocessed audio tensor [1, samples]
        """
        try:
            # Load audio using torchaudio
            waveform, orig_sr = torchaudio.load(str(audio_path))
            
            # Resample if needed
            if orig_sr != self.target_sample_rate:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=orig_sr,
                    new_freq=self.target_sample_rate
                )
                waveform = resampler(waveform)
            
            # Convert stereo to mono
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Normalize audio to [-1, 1]
            max_val = torch.abs(waveform).max()
            if max_val > 0:
                waveform = waveform / max_val
            
            # Pad or trim to max_length
            if waveform.shape[1] > self.max_length:
                # Trim to max_length
                waveform = waveform[:, :self.max_length]
            elif waveform.shape[1] < self.max_length:
                # Pad with zeros
                padding = self.max_length - waveform.shape[1]
                waveform = torch.nn.functional.pad(waveform, (0, padding))
            
            return waveform
            
        except Exception as e:
            logger.error(f"Error loading audio {audio_path}: {e}")
            # Return silence on error
            return torch.zeros(1, self.max_length)
    
    @staticmethod
    def from_directory(
        data_dir: Path,
        manifest_file: str = "manifest.json",
        **kwargs
    ) -> "MusicGenDataset":
        """
        Create dataset from a directory with a manifest file
        
        Manifest JSON format:
        [
            {
                "audio": "path/to/audio1.wav",
                "prompt": "upbeat rock guitar with distortion"
            },
            {
                "audio": "path/to/audio2.wav",
                "prompt": "slow jazz piano with smooth chords"
            }
        ]
        
        Args:
            data_dir: Root directory containing audio files and manifest
            manifest_file: Name of the manifest JSON file
            **kwargs: Additional arguments for MusicGenDataset
            
        Returns:
            MusicGenDataset instance
        """
        manifest_path = data_dir / manifest_file
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        
        # Load manifest
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Extract audio paths and prompts
        audio_files = []
        prompts = []
        
        for item in manifest:
            audio_path = data_dir / item["audio"]
            if audio_path.exists():
                audio_files.append(audio_path)
                prompts.append(item["prompt"])
            else:
                logger.warning(f"Audio file not found: {audio_path}")
        
        logger.info(f"Loaded {len(audio_files)} samples from {manifest_path}")
        
        return MusicGenDataset(
            audio_files=audio_files,
            prompts=prompts,
            **kwargs
        )


class AudioDataPreprocessor:
    """
    Utility class for batch preprocessing of audio datasets
    """
    
    def __init__(
        self,
        target_sample_rate: int = 32000,
        target_duration: float = 30.0
    ):
        self.target_sample_rate = target_sample_rate
        self.target_duration = target_duration
    
    def preprocess_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        create_manifest: bool = True
    ) -> int:
        """
        Batch preprocess all audio files in a directory
        
        Args:
            input_dir: Input directory with raw audio files
            output_dir: Output directory for preprocessed audio
            create_manifest: Whether to create a manifest.json file
            
        Returns:
            Number of files processed
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all audio files
        audio_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}
        audio_files = []
        
        for ext in audio_extensions:
            audio_files.extend(input_dir.glob(f"*{ext}"))
            audio_files.extend(input_dir.glob(f"*{ext.upper()}"))
        
        logger.info(f"Found {len(audio_files)} audio files in {input_dir}")
        
        manifest = []
        processed_count = 0
        
        for audio_file in audio_files:
            try:
                # Load audio
                waveform, orig_sr = torchaudio.load(str(audio_file))
                
                # Resample
                if orig_sr != self.target_sample_rate:
                    resampler = torchaudio.transforms.Resample(
                        orig_freq=orig_sr,
                        new_freq=self.target_sample_rate
                    )
                    waveform = resampler(waveform)
                
                # Convert to mono
                if waveform.shape[0] > 1:
                    waveform = torch.mean(waveform, dim=0, keepdim=True)
                
                # Normalize
                max_val = torch.abs(waveform).max()
                if max_val > 0:
                    waveform = waveform / max_val
                
                # Save preprocessed audio
                output_file = output_dir / f"{audio_file.stem}.wav"
                torchaudio.save(
                    str(output_file),
                    waveform,
                    self.target_sample_rate
                )
                
                # Add to manifest (use filename as default prompt)
                if create_manifest:
                    manifest.append({
                        "audio": output_file.name,
                        "prompt": audio_file.stem.replace('_', ' ').replace('-', ' ')
                    })
                
                processed_count += 1
                logger.info(f"Processed {audio_file.name} -> {output_file.name}")
                
            except Exception as e:
                logger.error(f"Error processing {audio_file}: {e}")
        
        # Save manifest
        if create_manifest and manifest:
            manifest_path = output_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Created manifest: {manifest_path}")
        
        logger.info(f"Preprocessing complete: {processed_count}/{len(audio_files)} files")
        
        return processed_count
    
    def compute_audio_statistics(
        self,
        audio_files: List[Path]
    ) -> Dict[str, Any]:
        """
        Compute statistics about audio dataset
        
        Returns:
            Dictionary with statistics (duration, sample rates, channels, etc.)
        """
        stats = {
            "num_files": len(audio_files),
            "total_duration": 0.0,
            "sample_rates": [],
            "num_channels": [],
            "durations": [],
            "file_sizes_mb": []
        }
        
        for audio_file in audio_files:
            try:
                info = torchaudio.info(str(audio_file))
                duration = info.num_frames / info.sample_rate
                file_size_mb = audio_file.stat().st_size / (1024 * 1024)
                
                stats["total_duration"] += duration
                stats["sample_rates"].append(info.sample_rate)
                stats["num_channels"].append(info.num_channels)
                stats["durations"].append(duration)
                stats["file_sizes_mb"].append(file_size_mb)
                
            except Exception as e:
                logger.warning(f"Could not read info for {audio_file}: {e}")
        
        # Compute summary statistics
        if stats["durations"]:
            stats["avg_duration"] = np.mean(stats["durations"])
            stats["min_duration"] = np.min(stats["durations"])
            stats["max_duration"] = np.max(stats["durations"])
            stats["total_size_gb"] = sum(stats["file_sizes_mb"]) / 1024
        
        logger.info(f"Dataset statistics:")
        logger.info(f"  Total files: {stats['num_files']}")
        logger.info(f"  Total duration: {stats['total_duration']/3600:.2f} hours")
        logger.info(f"  Avg duration: {stats.get('avg_duration', 0):.2f}s")
        logger.info(f"  Total size: {stats.get('total_size_gb', 0):.2f} GB")
        
        return stats


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Preprocess a directory of audio files
    preprocessor = AudioDataPreprocessor(target_sample_rate=32000, target_duration=30.0)
    
    input_dir = Path("./raw_audio")
    output_dir = Path("./preprocessed_audio")
    
    if input_dir.exists():
        preprocessor.preprocess_directory(input_dir, output_dir)
        
        # Load as dataset
        from transformers import AutoProcessor
        processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
        
        dataset = MusicGenDataset.from_directory(
            data_dir=output_dir,
            processor=processor
        )
        
        print(f"Dataset loaded with {len(dataset)} samples")
        sample = dataset[0]
        print(f"Sample keys: {sample.keys()}")
        print(f"Audio shape: {sample['audio_values'].shape}")
        print(f"Prompt: {sample['prompt']}")
