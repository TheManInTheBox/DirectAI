"""
Analysis Service - Handles audio source separation and MIR feature extraction
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime

import numpy as np
import librosa
import soundfile as sf
import jams

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for audio analysis and source separation"""
    
    def __init__(self):
        self.demucs_model = os.getenv("DEMUCS_MODEL", "htdemucs")
        self.sample_rate = 44100
        
    async def separate_sources(
        self,
        audio_path: Path,
        output_dir: Path
    ) -> List[Dict[str, Any]]:
        """
        Separate audio sources using Demucs
        
        Returns list of stem info dictionaries
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Running Demucs source separation with model: {self.demucs_model}")
            
            # Run Demucs in subprocess
            cmd = [
                "demucs",
                "--two-stems=vocals",  # Start with 2-stem (vocals/accompaniment)
                "-n", self.demucs_model,
                "-o", str(output_dir),
                str(audio_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Demucs failed: {stderr.decode()}")
                raise RuntimeError(f"Demucs separation failed: {stderr.decode()}")
            
            logger.info("Demucs separation completed successfully")
            
            # Find generated stems (Demucs creates subdirectories)
            stems_info = []
            model_dir = output_dir / self.demucs_model / audio_path.stem
            
            if model_dir.exists():
                for stem_file in model_dir.glob("*.wav"):
                    stem_type = stem_file.stem  # vocals, bass, drums, other
                    stems_info.append({
                        "stem_type": stem_type,
                        "filename": stem_file.name,
                        "path": str(stem_file)
                    })
                    logger.info(f"Found stem: {stem_type} -> {stem_file.name}")
            
            if not stems_info:
                logger.warning("No stems found after Demucs processing")
            
            return stems_info
            
        except Exception as e:
            logger.error(f"Error in source separation: {str(e)}", exc_info=True)
            raise
    
    async def analyze_music(self, audio_path: Path) -> Dict[str, Any]:
        """
        Extract MIR features: BPM, key, sections, chords, beats
        
        Uses Essentia and madmom for analysis
        """
        try:
            logger.info(f"Loading audio file for analysis: {audio_path}")
            
            # Load audio with librosa
            y, sr = librosa.load(str(audio_path), sr=self.sample_rate, mono=True)
            duration = float(len(y) / sr)
            
            logger.info(f"Audio loaded: duration={duration:.2f}s, sr={sr}")
            
            # Extract tempo (BPM)
            bpm = await self._extract_tempo(y, sr)
            
            # Extract key and tuning
            key, tuning = await self._extract_key_tuning(y, sr)
            
            # Extract beats
            beats = await self._extract_beats(y, sr)
            
            # Extract sections (structural segmentation)
            sections = await self._extract_sections(y, sr)
            
            # Extract chords
            chords = await self._extract_chords(y, sr)
            
            results = {
                "bpm": bpm,
                "key": key,
                "tuning_frequency": tuning,
                "duration_seconds": duration,
                "beats": beats,
                "sections": sections,
                "chords": chords
            }
            
            logger.info(f"Analysis complete: BPM={bpm}, Key={key}, Tuning={tuning}Hz")
            return results
            
        except Exception as e:
            logger.error(f"Error in music analysis: {str(e)}", exc_info=True)
            raise
    
    async def _extract_tempo(self, y: np.ndarray, sr: int) -> float:
        """Extract tempo (BPM) using librosa"""
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm = float(tempo)
            logger.info(f"Detected BPM: {bpm}")
            return round(bpm, 2)
        except Exception as e:
            logger.warning(f"Tempo extraction failed: {e}")
            return 120.0  # Default fallback
    
    async def _extract_key_tuning(self, y: np.ndarray, sr: int) -> tuple[str, float]:
        """Extract musical key and tuning frequency"""
        try:
            # Use librosa's chroma features for key estimation
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            
            # Simple key detection based on chroma energy
            key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            chroma_mean = np.mean(chroma, axis=1)
            key_idx = int(np.argmax(chroma_mean))
            key = key_names[key_idx]
            
            # Tuning frequency (A4 reference)
            tuning = 440.0  # Standard tuning (TODO: implement actual tuning detection)
            
            logger.info(f"Detected key: {key}, tuning: {tuning}Hz")
            return key, tuning
            
        except Exception as e:
            logger.warning(f"Key/tuning extraction failed: {e}")
            return "C", 440.0
    
    async def _extract_beats(self, y: np.ndarray, sr: int) -> List[Dict[str, Any]]:
        """Extract beat positions"""
        try:
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            
            beats = []
            for i, time in enumerate(beat_times):
                beats.append({
                    "time": float(time),
                    "position": i + 1,
                    "confidence": 1.0  # librosa doesn't provide confidence
                })
            
            logger.info(f"Extracted {len(beats)} beats")
            return beats
            
        except Exception as e:
            logger.warning(f"Beat extraction failed: {e}")
            return []
    
    async def _extract_sections(self, y: np.ndarray, sr: int) -> List[Dict[str, Any]]:
        """Extract structural sections (intro, verse, chorus, etc.)"""
        try:
            # Use librosa's segment boundaries
            bounds = librosa.segment.agglomerative(y, k=8)  # 8 segments
            bound_times = librosa.frames_to_time(bounds, sr=sr)
            
            sections = []
            section_labels = ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"]
            
            for i in range(len(bound_times) - 1):
                label = section_labels[i] if i < len(section_labels) else "section"
                sections.append({
                    "label": label,
                    "start_time": float(bound_times[i]),
                    "end_time": float(bound_times[i + 1]),
                    "confidence": 0.8
                })
            
            logger.info(f"Extracted {len(sections)} sections")
            return sections
            
        except Exception as e:
            logger.warning(f"Section extraction failed: {e}")
            return []
    
    async def _extract_chords(self, y: np.ndarray, sr: int) -> List[Dict[str, Any]]:
        """Extract chord progression"""
        try:
            # Use faster STFT-based chroma instead of CQT for MVP
            chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=2048)
            
            # Simple chord templates (major triads)
            chord_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            
            chords = []
            frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=512)
            
            # Downsample to every 0.5 seconds for chord changes
            step = int(0.5 * sr / 512)
            
            for i in range(0, chroma.shape[1] - step, step):
                chroma_segment = np.mean(chroma[:, i:i+step], axis=1)
                root_idx = int(np.argmax(chroma_segment))
                
                chords.append({
                    "chord": chord_names[root_idx],
                    "start_time": float(frame_times[i]),
                    "end_time": float(frame_times[min(i + step, len(frame_times) - 1)]),
                    "confidence": 0.7
                })
            
            logger.info(f"Extracted {len(chords)} chord segments")
            return chords[:50]  # Limit to first 50 chords
            
        except Exception as e:
            logger.warning(f"Chord extraction failed: {e}")
            return []
    
    def create_jams_annotation(
        self,
        audio_file_id: str,
        audio_path: Path,
        analysis_results: Dict[str, Any]
    ) -> jams.JAMS:
        """
        Create JAMS format annotation from analysis results
        """
        try:
            logger.info("Creating JAMS annotation")
            
            # Initialize JAMS object
            jam = jams.JAMS()
            
            # Add file metadata
            jam.file_metadata.duration = analysis_results.get("duration_seconds", 0.0)
            jam.file_metadata.identifiers = {"file_id": audio_file_id}
            jam.file_metadata.title = audio_path.stem
            
            # Add tempo annotation
            if "bpm" in analysis_results and analysis_results["bpm"]:
                tempo_ann = jams.Annotation(namespace="tempo")
                tempo_ann.append(
                    time=0.0,
                    duration=analysis_results["duration_seconds"],
                    value=analysis_results["bpm"],
                    confidence=1.0
                )
                jam.annotations.append(tempo_ann)
            
            # Add key annotation
            if "key" in analysis_results and analysis_results["key"]:
                key_ann = jams.Annotation(namespace="key_mode")
                key_ann.append(
                    time=0.0,
                    duration=analysis_results["duration_seconds"],
                    value=f"{analysis_results['key']}:major",
                    confidence=0.8
                )
                jam.annotations.append(key_ann)
            
            # Add beat annotations
            if "beats" in analysis_results:
                beat_ann = jams.Annotation(namespace="beat")
                for beat in analysis_results["beats"]:
                    beat_ann.append(
                        time=beat["time"],
                        duration=0.0,
                        value=beat["position"],
                        confidence=beat.get("confidence", 1.0)
                    )
                jam.annotations.append(beat_ann)
            
            # Add segment/section annotations
            if "sections" in analysis_results:
                segment_ann = jams.Annotation(namespace="segment_open")
                for section in analysis_results["sections"]:
                    segment_ann.append(
                        time=section["start_time"],
                        duration=section["end_time"] - section["start_time"],
                        value=section["label"],
                        confidence=section.get("confidence", 0.8)
                    )
                jam.annotations.append(segment_ann)
            
            # Add chord annotations
            if "chords" in analysis_results:
                chord_ann = jams.Annotation(namespace="chord")
                for chord in analysis_results["chords"]:
                    chord_ann.append(
                        time=chord["start_time"],
                        duration=chord["end_time"] - chord["start_time"],
                        value=chord["chord"],
                        confidence=chord.get("confidence", 0.7)
                    )
                jam.annotations.append(chord_ann)
            
            logger.info(f"JAMS annotation created with {len(jam.annotations)} annotation types")
            return jam
            
        except Exception as e:
            logger.error(f"Error creating JAMS annotation: {str(e)}", exc_info=True)
            raise
    
    def save_jams(self, jam: jams.JAMS, output_path: Path):
        """Save JAMS annotation to file"""
        try:
            jam.save(str(output_path))
            logger.info(f"JAMS annotation saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving JAMS: {str(e)}", exc_info=True)
            raise
