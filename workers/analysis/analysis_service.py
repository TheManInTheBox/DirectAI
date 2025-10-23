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

# Import music theory analyzer
from music_theory_analyzer import MusicTheoryAnalyzer

# Add mutagen for MP3 metadata extraction
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3NoHeaderError
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logging.warning("Mutagen not available - MP3 metadata extraction disabled")

# Add music transcription libraries
try:
    import music21
    import pretty_midi
    import mir_eval
    NOTATION_AVAILABLE = True
except ImportError:
    NOTATION_AVAILABLE = False
    logging.warning("Music notation libraries not available - notation extraction disabled")

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for audio analysis and source separation"""
    
    def __init__(self):
        self.demucs_model = os.getenv("DEMUCS_MODEL", "htdemucs")
        self.sample_rate = 44100
        self.theory_analyzer = MusicTheoryAnalyzer()
    
    async def extract_mp3_metadata(self, audio_path: Path) -> Dict[str, Any]:
        """
        Extract MP3 metadata (ID3 tags) from the original audio file
        Returns metadata dict and album artwork data if present
        """
        metadata = {}
        
        if not MUTAGEN_AVAILABLE:
            logger.warning("Mutagen not available - skipping MP3 metadata extraction")
            return metadata
        
        try:
            logger.info(f"Extracting MP3 metadata from: {audio_path}")
            
            # Load the audio file with mutagen
            audio_file = MutagenFile(str(audio_path))
            
            if audio_file is None:
                logger.warning("Could not read audio file metadata")
                return metadata
            
            # Extract common ID3 tags
            tag_mappings = {
                'TIT2': 'title',           # Title
                'TPE1': 'artist',          # Artist
                'TALB': 'album',           # Album
                'TDRC': 'year',            # Year
                'TPE2': 'album_artist',    # Album Artist
                'TCON': 'genre',           # Genre
                'TRCK': 'track_number',    # Track Number
                'TPE3': 'conductor',       # Conductor
                'TCOM': 'composer',        # Composer
                'TPOS': 'disc_number',     # Disc Number
                'TBPM': 'bpm_tag',         # BPM from tag
                'TKEY': 'key_tag',         # Key from tag
                'COMM::eng': 'comment',    # Comment
            }
            
            # Extract tags
            for tag_id, field_name in tag_mappings.items():
                if tag_id in audio_file:
                    tag_value = audio_file[tag_id]
                    if hasattr(tag_value, 'text') and tag_value.text:
                        metadata[field_name] = str(tag_value.text[0])
                    else:
                        metadata[field_name] = str(tag_value)
            
            # Extract album artwork if present
            if 'APIC:' in audio_file or 'APIC' in audio_file:
                try:
                    apic_tag = audio_file.get('APIC:') or audio_file.get('APIC')
                    if apic_tag and hasattr(apic_tag, 'data'):
                        metadata['album_artwork_data'] = apic_tag.data
                        metadata['album_artwork_mime'] = apic_tag.mime
                        logger.info(f"Found album artwork: {len(apic_tag.data)} bytes, type: {apic_tag.mime}")
                except Exception as art_error:
                    logger.warning(f"Error extracting album artwork: {art_error}")
            
            # Extract technical information
            if hasattr(audio_file, 'info'):
                info = audio_file.info
                metadata.update({
                    'bitrate': getattr(info, 'bitrate', None),
                    'length_seconds': getattr(info, 'length', None),
                    'channels': getattr(info, 'channels', None),
                    'sample_rate': getattr(info, 'sample_rate', None),
                    'mode': getattr(info, 'mode', None),  # Stereo/Mono
                    'version': getattr(info, 'version', None),  # MP3 version
                })
            
            # Log extracted metadata
            logger.info(f"Extracted MP3 metadata: {len(metadata)} fields")
            if 'title' in metadata and 'artist' in metadata:
                logger.info(f"Track: {metadata['artist']} - {metadata['title']}")
            
            return metadata
            
        except ID3NoHeaderError:
            logger.warning("No ID3 header found in audio file")
            return metadata
        except Exception as e:
            logger.error(f"Error extracting MP3 metadata: {str(e)}", exc_info=True)
            return metadata
        
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
            
            # Run Demucs in subprocess for 4-stem separation
            cmd = [
                "demucs",
                # Remove --two-stems to get full 4-stem separation: vocals, drums, bass, other
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
            
            # === MVP ANALYSIS ===
            # Extract essential features: BPM, Key, Chords, basic metadata
            logger.info("Running MVP analysis (optimized for performance)")
            
            # Extract tempo (BPM)
            bpm = await self._extract_tempo(y, sr)
            
            # Extract key and tuning
            key, tuning = await self._extract_key_tuning(y, sr)
            
            # Extract chords (has 30s timeout)
            logger.info("Extracting chord progression...")
            chords = await self._extract_chords(y, sr)
            logger.info(f"Chord extraction complete: {len(chords)} chords extracted")
            
            # Simple beat extraction (minimal)
            logger.info("Extracting basic beats...")
            beats = await self._extract_beats(y, sr)
            logger.info(f"Beat extraction complete: {len(beats)} beats extracted")
            
            # Skip intensive analysis features for MVP
            logger.info("Skipping intensive analysis (sections, theory, technical, spectral, temporal)")
            sections = []
            harmonic_analysis = {}
            rhythmic_analysis = {"complexity_score": 0.0}
            genre_analysis = {"primary_genre": "unknown"}
            technical_features = {}
            psychoacoustic_features = {}
            spectral_features = {}
            temporal_features = {}
            
            results = {
                "bpm": bpm,
                "key": key,
                "tuning_frequency": tuning,
                "duration_seconds": duration,
                "beats": beats,
                "sections": sections,
                "chords": chords,
                "harmonic_analysis": harmonic_analysis,
                "rhythmic_analysis": rhythmic_analysis,
                "genre_analysis": genre_analysis,
                "technical_features": technical_features,
                "psychoacoustic_features": psychoacoustic_features,
                "spectral_features": spectral_features,
                "temporal_features": temporal_features,
                "bark_training_data": {}  # Skip Bark training data for MVP performance
            }
            
            logger.info(f"Simplified analysis complete: BPM={bpm}, Key={key}, Tuning={tuning}Hz, Duration={duration:.1f}s")
            return results
            
        except Exception as e:
            logger.error(f"Error in music analysis: {str(e)}", exc_info=True)
            raise

    async def _extract_comprehensive_technical_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Compute core technical audio features used by training/export.

        Returns at least these fields:
        - sample_rate (int)
        - bit_depth (int, best-effort, default 16)
        - dynamic_range (float, dB)
        - peak_level (float, dBFS-like)
        - rms_level (float, dBFS-like)
        - crest_factor_db (float)
        - zero_crossing_rate_mean (float)
        """
        try:
            rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
            peak_amplitude = float(np.max(np.abs(y)) if len(y) > 0 else 0.0)
            # Avoid log of zero
            rms_mean = float(np.mean(rms)) if rms.size > 0 else 1e-10
            rms_min = float(np.min(rms)) if rms.size > 0 else 1e-10

            dynamic_range_db = float(20 * np.log10((np.max(rms) + 1e-10) / (rms_min + 1e-10))) if rms.size > 0 else 0.0
            peak_db = float(20 * np.log10(peak_amplitude + 1e-10))
            rms_db = float(20 * np.log10(rms_mean + 1e-10))
            crest_factor_db = peak_db - rms_db
            zcr_mean = float(np.mean(librosa.zero_crossings(y))) if len(y) > 0 else 0.0

            return {
                "sample_rate": int(sr),
                "bit_depth": 16,  # best-effort default; original depth often unknown here
                "dynamic_range": round(dynamic_range_db, 2),
                "peak_level": round(peak_db, 2),
                "rms_level": round(rms_db, 2),
                "crest_factor_db": round(crest_factor_db, 2),
                "zero_crossing_rate_mean": zcr_mean,
            }
        except Exception as e:
            logger.warning(f"Technical feature extraction failed: {e}")
            return {
                "sample_rate": int(sr),
                "bit_depth": 16,
                "dynamic_range": 0.0,
                "peak_level": 0.0,
                "rms_level": 0.0,
                "crest_factor_db": 0.0,
                "zero_crossing_rate_mean": 0.0,
            }

    async def _extract_technical_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Compatibility wrapper for stem analysis to compute technical features."""
        return await self._extract_comprehensive_technical_features(y, sr)

    async def _extract_psychoacoustic_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Wrapper that returns concise psychoacoustic features derived from the detailed set."""
        try:
            # Run in executor to allow timeout to work with blocking CPU operations
            loop = asyncio.get_event_loop()
            detailed = await loop.run_in_executor(
                None, 
                self._extract_detailed_psychoacoustic_features,
                y,
                sr
            )
            loud = detailed.get("perceived_loudness", {})
            sharp = detailed.get("sharpness", {})
            rough = detailed.get("roughness", {})
            return {
                "loudness_mean": float(loud.get("loudness_mean", 0.0)),
                "loudness_std": float(loud.get("loudness_std", 0.0)),
                "loudness_range_lu": float(loud.get("loudness_range_lu", 0.0)),
                "sharpness_coefficient": float(sharp.get("sharpness_coefficient", 0.0)),
                "perceived_brightness": sharp.get("perceived_brightness", ""),
                "overall_roughness": float(rough.get("overall_roughness", 0.0)),
                "roughness_variation": float(rough.get("roughness_variation", 0.0)),
            }
        except Exception as e:
            logger.warning(f"Psychoacoustic feature extraction failed: {e}")
            return {}

    async def _extract_spectral_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Compute compact spectral features used downstream.

        Produces keys expected by training/export helpers:
        - spectral_centroid_mean, spectral_bandwidth_mean, spectral_contrast_mean (list), harmonic_ratio
        """
        try:
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
            spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)

            # Harmonic content ratio via HPSS
            harmonic, percussive = librosa.effects.hpss(y)
            harmonic_energy = float(np.sum(harmonic ** 2))
            total_energy = float(np.sum(y ** 2)) + 1e-10
            harmonic_ratio = harmonic_energy / total_energy

            return {
                "spectral_centroid_mean": float(np.mean(spectral_centroid)) if spectral_centroid.size else 0.0,
                "spectral_bandwidth_mean": float(np.mean(spectral_bandwidth)) if spectral_bandwidth.size else 0.0,
                "spectral_contrast_mean": [float(np.mean(spectral_contrast[i])) for i in range(spectral_contrast.shape[0])] if spectral_contrast.size else [],
                "harmonic_ratio": float(harmonic_ratio),
            }
        except Exception as e:
            logger.warning(f"Spectral feature extraction failed: {e}")
            return {
                "spectral_centroid_mean": 0.0,
                "spectral_bandwidth_mean": 0.0,
                "spectral_contrast_mean": [],
                "harmonic_ratio": 0.0,
            }

    async def _extract_temporal_features(self, y: np.ndarray, sr: int, beats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize temporal features; aligns with training data needs."""
        try:
            duration = float(len(y) / sr) if sr > 0 else 0.0
            beat_times = [b.get("time", 0.0) for b in (beats or [])]
            beat_count = len(beat_times)
            ioi = np.diff(beat_times) if beat_count > 1 else np.array([])
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)

            return {
                "duration_seconds": duration,
                "beat_count": beat_count,
                "beats_per_second": float(beat_count / duration) if duration > 0 else 0.0,
                "inter_onset_interval_mean": float(np.mean(ioi)) if ioi.size else 0.0,
                "inter_onset_interval_std": float(np.std(ioi)) if ioi.size else 0.0,
                "onset_strength_mean": float(np.mean(onset_env)) if onset_env.size else 0.0,
                "onset_strength_std": float(np.std(onset_env)) if onset_env.size else 0.0,
            }
        except Exception as e:
            logger.warning(f"Temporal feature extraction failed: {e}")
            return {
                "duration_seconds": 0.0,
                "beat_count": 0,
                "beats_per_second": 0.0,
                "inter_onset_interval_mean": 0.0,
                "inter_onset_interval_std": 0.0,
                "onset_strength_mean": 0.0,
                "onset_strength_std": 0.0,
            }
    
    async def _extract_tempo(self, y: np.ndarray, sr: int) -> float:
        """Extract tempo (BPM) using librosa with improved accuracy"""
        try:
            logger.info("Computing onset envelope for tempo detection...")
            # Use onset detection for more accurate tempo estimation with timeout
            try:
                loop = asyncio.get_event_loop()
                onset_envelope = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: librosa.onset.onset_strength(
                            y=y, sr=sr,
                            hop_length=512,
                            aggregate=np.median
                        )
                    ),
                    timeout=30.0  # 30 second timeout
                )
                logger.info("Onset envelope computed")
            except asyncio.TimeoutError:
                logger.warning("Tempo onset detection timed out, using default BPM")
                return 120.0  # Fallback to 120 BPM
            
            # Extract multiple tempo candidates with timeout
            logger.info("Detecting tempo candidates...")
            try:
                loop = asyncio.get_event_loop()
                tempo_candidates = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: librosa.beat.tempo(
                            onset_envelope=onset_envelope, 
                            sr=sr,
                            hop_length=512,
                            start_bpm=120.0,
                            std_bpm=1.0,
                            ac_size=8.0,
                            max_tempo=180.0,
                            aggregate=None
                        )
                    ),
                    timeout=30.0  # 30 second timeout
                )
                logger.info(f"Tempo detection completed, found {len(tempo_candidates)} candidates")
            except asyncio.TimeoutError:
                logger.warning("Tempo detection timed out, using default BPM")
                return 120.0  # Fallback to 120 BPM
            
            # If we get multiple candidates, pick the most reasonable one
            if len(tempo_candidates) > 1:
                # Prefer tempos in the typical range (80-140 BPM)
                reasonable_candidates = [t for t in tempo_candidates if 80 <= t <= 140]
                if reasonable_candidates:
                    bpm = float(reasonable_candidates[0])  # Take the first reasonable one
                else:
                    bpm = float(tempo_candidates[0])
            else:
                bpm = float(tempo_candidates[0])
            
            # If tempo is still too high, it might be detecting subdivisions
            if bpm > 160:
                # Try halving the tempo (detecting 16th notes instead of quarter notes)
                bpm_half = bpm / 2
                if 60 <= bpm_half <= 140:
                    logger.info(f"High tempo detected ({bpm:.1f}), using half tempo: {bpm_half:.1f}")
                    bpm = bpm_half
                else:
                    # Try quartering the tempo (detecting 32nd notes)
                    bpm_quarter = bpm / 4
                    if 60 <= bpm_quarter <= 140:
                        logger.info(f"Very high tempo detected ({bpm:.1f}), using quarter tempo: {bpm_quarter:.1f}")
                        bpm = bpm_quarter
            
            # Final sanity check
            if bpm < 60 or bpm > 180:
                logger.warning(f"Unrealistic tempo detected ({bpm:.1f}), using default")
                bpm = 120.0
            
            logger.info(f"Detected BPM: {bpm}")
            return round(bpm, 2)
        except Exception as e:
            logger.warning(f"Tempo extraction failed: {e}")
            return 120.0  # Default fallback
    
    async def _extract_key_tuning(self, y: np.ndarray, sr: int) -> tuple[str, float]:
        """Extract musical key and tuning frequency with improved accuracy"""
        try:
            # Use more robust chroma features
            chroma = librosa.feature.chroma_cqt(
                y=y, sr=sr, 
                hop_length=512,
                fmin=librosa.note_to_hz('C1'),
                n_chroma=12,
                bins_per_octave=36  # Higher resolution
            )
            
            # Calculate chroma profiles for major and minor keys
            # Krumhansl-Schmuckler key profiles (simplified)
            major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
            minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
            
            # Normalize profiles
            major_profile = major_profile / np.sum(major_profile)
            minor_profile = minor_profile / np.sum(minor_profile)
            
            # Get mean chroma vector
            chroma_mean = np.mean(chroma, axis=1)
            chroma_mean = chroma_mean / np.sum(chroma_mean)  # Normalize
            
            key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            
            # Calculate correlations with all 24 keys (12 major + 12 minor)
            correlations = []
            
            for i in range(12):
                # Rotate profiles to match current key
                major_rotated = np.roll(major_profile, i)
                minor_rotated = np.roll(minor_profile, i)
                
                # Calculate correlation with observed chroma
                major_corr = np.corrcoef(chroma_mean, major_rotated)[0, 1]
                minor_corr = np.corrcoef(chroma_mean, minor_rotated)[0, 1]
                
                # Handle NaN correlations
                if np.isnan(major_corr):
                    major_corr = 0.0
                if np.isnan(minor_corr):
                    minor_corr = 0.0
                
                correlations.append((major_corr, key_names[i], 'major'))
                correlations.append((minor_corr, key_names[i], 'minor'))
            
            # Find best match
            best_corr, best_key, best_mode = max(correlations, key=lambda x: x[0])
            
            # Format key
            if best_mode == 'major':
                key = f"{best_key} major"
            else:
                key = f"{best_key} minor"
            
            # Tuning frequency detection (simplified - actual implementation would be complex)
            tuning = 440.0  # Standard A4 tuning
            
            logger.info(f"Detected key: {key}, tuning: {tuning}Hz (correlation: {best_corr:.3f})")
            return key, tuning
            
        except Exception as e:
            logger.warning(f"Key/tuning extraction failed: {e}")
            return "C major", 440.0
    
    async def _extract_beats(self, y: np.ndarray, sr: int) -> List[Dict[str, Any]]:
        """Extract beat positions with improved accuracy"""
        try:
            # First get the corrected tempo using our improved method
            corrected_bpm = await self._extract_tempo(y, sr)
            
            logger.info("Computing onset envelope for beat tracking...")
            
            # Use more robust onset detection with timeout
            try:
                loop = asyncio.get_event_loop()
                onset_envelope = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: librosa.onset.onset_strength(
                            y=y, sr=sr, 
                            hop_length=512,
                            aggregate=np.median
                        )
                    ),
                    timeout=30.0  # 30 second timeout for onset detection
                )
                logger.info("Onset envelope computed successfully")
            except asyncio.TimeoutError:
                logger.warning("Onset envelope computation timed out after 30 seconds, using synthetic beats")
                # Create synthetic beats based on BPM
                duration = len(y) / sr
                beats = []
                beat_interval = 60.0 / corrected_bpm
                time = 0.0
                position = 1
                while time < duration:
                    beats.append({
                        "time": time,
                        "position": position,
                        "confidence": 0.5
                    })
                    time += beat_interval
                    position += 1
                logger.info(f"Created {len(beats)} synthetic beats (tempo: {corrected_bpm:.2f} BPM)")
                return beats
            
            # Track beats with the corrected tempo with timeout
            logger.info("Tracking beat positions...")
            try:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: librosa.beat.beat_track(
                            onset_envelope=onset_envelope,
                            sr=sr,
                            hop_length=512,
                            bpm=corrected_bpm,
                            trim=False,
                            tightness=100
                        )
                    ),
                    timeout=30.0  # 30 second timeout for beat tracking
                )
                _, beat_frames = result
                logger.info("Beat tracking completed successfully")
            except asyncio.TimeoutError:
                logger.warning("Beat tracking timed out after 30 seconds, using synthetic beats")
                # Create synthetic beats based on BPM
                duration = len(y) / sr
                beats = []
                beat_interval = 60.0 / corrected_bpm
                time = 0.0
                position = 1
                while time < duration:
                    beats.append({
                        "time": time,
                        "position": position,
                        "confidence": 0.5
                    })
                    time += beat_interval
                    position += 1
                logger.info(f"Created {len(beats)} synthetic beats (tempo: {corrected_bpm:.2f} BPM)")
                return beats
            
            beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=512)
            
            beats = []
            for i, time in enumerate(beat_times):
                beats.append({
                    "time": float(time),
                    "position": i + 1,
                    "confidence": 0.8  # Moderate confidence for librosa
                })
            
            # Sanity check based on corrected tempo
            duration = len(y) / sr
            expected_beats = int((corrected_bpm * duration) / 60.0)
            actual_beats = len(beats)
            
            # If the beat count is way off from expected, create synthetic beats
            if abs(actual_beats - expected_beats) > expected_beats * 0.5:  # More than 50% off
                logger.warning(f"Beat count mismatch (expected ~{expected_beats}, got {actual_beats}), using synthetic beats")
                beats = []
                beat_interval = 60.0 / corrected_bpm
                time = 0.0
                position = 1
                while time < duration:
                    beats.append({
                        "time": time,
                        "position": position,
                        "confidence": 0.6  # Lower confidence for synthetic beats
                    })
                    time += beat_interval
                    position += 1
            
            logger.info(f"Extracted {len(beats)} beats (corrected tempo: {corrected_bpm:.2f} BPM)")
            return beats
            
        except Exception as e:
            logger.warning(f"Beat extraction failed: {e}")
            return []
    
    async def _extract_sections(self, y: np.ndarray, sr: int) -> List[Dict[str, Any]]:
        """Extract structural sections (intro, verse, chorus, etc.)"""
        try:
            logger.info("Starting librosa agglomerative clustering for section detection...")
            
            # For long audio files, use fewer segments and simpler features to avoid hanging
            duration = len(y) / sr
            k = min(6, max(3, int(duration / 30)))  # Adaptive: 1 segment per 30 seconds, max 6
            
            logger.info(f"Using k={k} segments for {duration:.1f}s audio")
            
            # Run the potentially slow operation with a timeout
            # Use asyncio.wait_for with a timeout of 60 seconds
            try:
                # We need to run the blocking operation in an executor
                loop = asyncio.get_event_loop()
                bounds = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, 
                        lambda: librosa.segment.agglomerative(y, k=k)
                    ),
                    timeout=60.0  # 60 second timeout
                )
                logger.info(f"Agglomerative clustering complete: {len(bounds)} boundaries found")
            except asyncio.TimeoutError:
                logger.warning(f"Section extraction timed out after 60 seconds, using simple duration-based sections")
                # Fallback: create simple time-based sections
                num_sections = k
                section_duration = duration / num_sections
                bound_times = [i * section_duration for i in range(num_sections + 1)]
                
                sections = []
                section_labels = ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"]
                
                for i in range(len(bound_times) - 1):
                    label = section_labels[i] if i < len(section_labels) else "section"
                    sections.append({
                        "label": label,
                        "start_time": float(bound_times[i]),
                        "end_time": float(bound_times[i + 1]),
                        "confidence": 0.5  # Lower confidence for fallback
                    })
                
                logger.info(f"Created {len(sections)} fallback sections")
                return sections
            
            # Convert frame indices to time
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
            logger.info("Starting STFT-based chroma analysis for chord detection...")
            
            # Run the potentially slow operation with a timeout
            try:
                loop = asyncio.get_event_loop()
                chroma = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: librosa.feature.chroma_stft(y=y, sr=sr, hop_length=2048)
                    ),
                    timeout=30.0  # 30 second timeout
                )
                logger.info(f"Chroma extraction complete: shape={chroma.shape}")
            except asyncio.TimeoutError:
                logger.warning("Chord extraction timed out after 30 seconds, skipping chords")
                return []
            
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
                
                # Parse key format - analysis_results['key'] is like "C# major" or "A minor"
                key_str = analysis_results["key"]
                if " " in key_str:
                    key_parts = key_str.split(" ")
                    key_root = key_parts[0]  # e.g., "C#"
                    key_mode = key_parts[1]  # e.g., "major"
                    jams_key = f"{key_root}:{key_mode}"  # e.g., "C#:major"
                else:
                    jams_key = key_str  # Use as-is if no space
                
                key_ann.append(
                    time=0.0,
                    duration=analysis_results["duration_seconds"],
                    value=jams_key,
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

    async def analyze_stem_comprehensive(self, stem_path: Path, stem_type: str) -> Dict[str, Any]:
        """Comprehensive analysis of individual stems for Bark training"""
        try:
            logger.info(f"Starting comprehensive stem analysis for {stem_type}: {stem_path}")
            
            # Load audio
            y, sr = librosa.load(str(stem_path), sr=self.sample_rate, mono=True)
            duration = float(len(y) / sr)
            
            # Basic analysis
            bpm = await self._extract_tempo(y, sr)
            key, tuning = await self._extract_key_tuning(y, sr)
            
            # Technical features
            technical_features = await self._extract_technical_features(y, sr)
            spectral_features = await self._extract_spectral_features(y, sr)
            
            # Psychoacoustic features (with timeout)
            try:
                psychoacoustic_features = await asyncio.wait_for(
                    self._extract_psychoacoustic_features(y, sr),
                    timeout=30.0
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Psychoacoustic analysis failed for stem: {e}")
                psychoacoustic_features = {}
            
            # Stem-specific analysis
            stem_characteristics = await self._analyze_stem_characteristics(y, sr, stem_type)
            
            # Prepare Bark training data for this stem (without Flamingo)
            bark_training_data = await self._prepare_stem_bark_training_data(
                stem_path, stem_type, bpm, key, duration,
                {}, technical_features, spectral_features, 
                psychoacoustic_features, stem_characteristics
            )
            
            results = {
                "stem_type": stem_type,
                "stem_path": str(stem_path),
                "duration_seconds": duration,
                "bpm": bpm,
                "key": key,
                "tuning_frequency": tuning,
                "technical_features": technical_features,
                "spectral_features": spectral_features,
                "psychoacoustic_features": psychoacoustic_features,
                "stem_characteristics": stem_characteristics,
                "bark_training_data": bark_training_data,
                "notation_data": await self.extract_notation(stem_path, stem_type, sr)
            }
            
            logger.info(f"Comprehensive stem analysis completed for {stem_type}")
            return results
            
        except Exception as e:
            logger.error(f"Error in comprehensive stem analysis: {str(e)}", exc_info=True)
            return {"error": str(e), "stem_type": stem_type}
    
    async def _analyze_stem_characteristics(self, y: np.ndarray, sr: int, stem_type: str) -> Dict[str, Any]:
        """Analyze characteristics specific to each stem type"""
        try:
            characteristics = {
                "stem_type": stem_type,
                "energy_profile": {},
                "frequency_profile": {},
                "temporal_profile": {},
                "stem_specific_features": {}
            }
            
            # Energy analysis
            rms_energy = librosa.feature.rms(y=y, hop_length=512)[0]
            characteristics["energy_profile"] = {
                "mean_energy": float(np.mean(rms_energy)),
                "energy_variance": float(np.var(rms_energy)),
                "peak_energy": float(np.max(rms_energy)),
                "energy_distribution": [float(x) for x in np.histogram(rms_energy, bins=10)[0]]
            }
            
            # Frequency analysis
            stft = librosa.stft(y, hop_length=512)
            magnitude = np.abs(stft)
            
            # Frequency bands analysis
            freqs = librosa.fft_frequencies(sr=sr)
            low_band = magnitude[freqs < 250].mean()
            mid_band = magnitude[(freqs >= 250) & (freqs < 4000)].mean()
            high_band = magnitude[freqs >= 4000].mean()
            
            characteristics["frequency_profile"] = {
                "low_frequency_energy": float(low_band),
                "mid_frequency_energy": float(mid_band),
                "high_frequency_energy": float(high_band),
                "frequency_centroid": float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
                "frequency_bandwidth": float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
            }
            
            # Stem-specific analysis
            if stem_type.lower() == "drums":
                characteristics["stem_specific_features"] = await self._analyze_drum_characteristics(y, sr)
            elif stem_type.lower() == "bass":
                characteristics["stem_specific_features"] = await self._analyze_bass_characteristics(y, sr)
            elif stem_type.lower() == "vocals":
                characteristics["stem_specific_features"] = await self._analyze_vocal_characteristics(y, sr)
            elif stem_type.lower() in ["other", "guitar", "keys", "synth"]:
                characteristics["stem_specific_features"] = await self._analyze_harmonic_characteristics(y, sr)
            
            return characteristics
            
        except Exception as e:
            logger.error(f"Error analyzing stem characteristics: {str(e)}")
            return {"error": str(e)}
    
    async def _analyze_drum_characteristics(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze drum-specific characteristics"""
        # Onset detection for drum hits
        onset_frames = librosa.onset.onset_detect(
            y=y, sr=sr, units='time', hop_length=512, backtrack=True
        )
        
        # Tempo analysis specific to drums
        tempo_histogram = librosa.beat.tempo(y=y, sr=sr, aggregate=None)
        
        return {
            "onset_density": len(onset_frames) / (len(y) / sr),
            "drum_hits": len(onset_frames),
            "rhythmic_complexity": float(np.std(np.diff(onset_frames)) if len(onset_frames) > 1 else 0),
            "tempo_stability": float(np.std(tempo_histogram)) if len(tempo_histogram) > 1 else 0,
            "kick_drum_presence": self._detect_kick_drum_presence(y, sr),
            "snare_presence": self._detect_snare_presence(y, sr),
            "hihat_presence": self._detect_hihat_presence(y, sr)
        }
    
    async def _analyze_bass_characteristics(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze bass-specific characteristics"""
        # Pitch tracking for bass
        pitches, magnitudes = librosa.piptrack(
            y=y, sr=sr, threshold=0.1, fmin=40, fmax=400
        )
        
        # Extract fundamental frequency
        fundamental_freqs = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                fundamental_freqs.append(pitch)
        
        return {
            "fundamental_frequency_range": [float(min(fundamental_freqs)), float(max(fundamental_freqs))] if fundamental_freqs else [0, 0],
            "pitch_stability": float(np.std(fundamental_freqs)) if fundamental_freqs else 0,
            "note_changes": len([i for i in range(1, len(fundamental_freqs)) if abs(fundamental_freqs[i] - fundamental_freqs[i-1]) > 10]) if len(fundamental_freqs) > 1 else 0,
            "bass_register_energy": self._calculate_bass_register_energy(y, sr),
            "sub_bass_presence": self._detect_sub_bass_presence(y, sr)
        }
    
    async def _analyze_vocal_characteristics(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze vocal-specific characteristics"""
        # Pitch tracking for vocals
        pitches, magnitudes = librosa.piptrack(
            y=y, sr=sr, threshold=0.1, fmin=80, fmax=800
        )
        
        # Voice activity detection (simple energy-based)
        rms_energy = librosa.feature.rms(y=y, hop_length=512)[0]
        voice_activity = rms_energy > (np.mean(rms_energy) * 0.3)
        
        return {
            "vocal_range_hz": self._calculate_vocal_range(pitches, magnitudes),
            "voice_activity_ratio": float(np.sum(voice_activity) / len(voice_activity)),
            "formant_characteristics": self._analyze_formants(y, sr),
            "vibrato_presence": self._detect_vibrato(pitches, magnitudes),
            "breath_sounds": self._detect_breath_sounds(y, sr)
        }
    
    async def _analyze_harmonic_characteristics(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze harmonic instrument characteristics"""
        # Harmonic analysis
        harmonic = librosa.effects.harmonic(y)
        percussive = librosa.effects.percussive(y)
        
        harmonic_ratio = np.mean(harmonic ** 2) / (np.mean(y ** 2) + 1e-10)
        
        return {
            "harmonic_ratio": float(harmonic_ratio),
            "harmonic_content_strength": float(np.mean(harmonic ** 2)),
            "percussive_elements": float(np.mean(percussive ** 2)),
            "chord_changes": self._detect_chord_changes(y, sr),
            "sustained_notes": self._detect_sustained_notes(y, sr)
        }
    
    def _detect_kick_drum_presence(self, y: np.ndarray, sr: int) -> float:
        """Detect kick drum presence (low frequency, short duration)"""
        # Focus on low frequencies (20-100 Hz)
        low_freq_energy = np.mean(y ** 2)  # Simplified
        return float(low_freq_energy)
    
    def _detect_snare_presence(self, y: np.ndarray, sr: int) -> float:
        """Detect snare presence (mid frequency, sharp attack)"""
        # Focus on mid frequencies with sharp attacks
        return float(np.mean(np.abs(np.diff(y))))  # Simplified attack detection
    
    def _detect_hihat_presence(self, y: np.ndarray, sr: int) -> float:
        """Detect hi-hat presence (high frequency, short duration)"""
        # High frequency energy
        stft = librosa.stft(y)
        high_freq_energy = np.mean(np.abs(stft[int(len(stft) * 0.7):]))
        return float(high_freq_energy)
    
    def _calculate_bass_register_energy(self, y: np.ndarray, sr: int) -> float:
        """Calculate energy in bass register (20-200 Hz)"""
        stft = librosa.stft(y)
        freqs = librosa.fft_frequencies(sr=sr)
        bass_indices = (freqs >= 20) & (freqs <= 200)
        bass_energy = np.mean(np.abs(stft[bass_indices]))
        return float(bass_energy)
    
    def _detect_sub_bass_presence(self, y: np.ndarray, sr: int) -> float:
        """Detect sub-bass presence (20-60 Hz)"""
        stft = librosa.stft(y)
        freqs = librosa.fft_frequencies(sr=sr)
        sub_bass_indices = (freqs >= 20) & (freqs <= 60)
        sub_bass_energy = np.mean(np.abs(stft[sub_bass_indices]))
        return float(sub_bass_energy)
    
    def _calculate_vocal_range(self, pitches: np.ndarray, magnitudes: np.ndarray) -> List[float]:
        """Calculate vocal range from pitch tracking"""
        valid_pitches = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                valid_pitches.append(pitch)
        
        if valid_pitches:
            return [float(min(valid_pitches)), float(max(valid_pitches))]
        return [0.0, 0.0]
    
    def _analyze_formants(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """Analyze formant characteristics (simplified)"""
        # This is a simplified formant analysis
        stft = librosa.stft(y)
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Focus on typical formant ranges
        f1_range = (300, 1000)  # First formant
        f2_range = (900, 3000)  # Second formant
        
        f1_indices = (freqs >= f1_range[0]) & (freqs <= f1_range[1])
        f2_indices = (freqs >= f2_range[0]) & (freqs <= f2_range[1])
        
        f1_energy = float(np.mean(np.abs(stft[f1_indices])))
        f2_energy = float(np.mean(np.abs(stft[f2_indices])))
        
        return {
            "f1_energy": f1_energy,
            "f2_energy": f2_energy,
            "formant_ratio": f2_energy / (f1_energy + 1e-10)
        }
    
    def _detect_vibrato(self, pitches: np.ndarray, magnitudes: np.ndarray) -> float:
        """Detect vibrato in vocal performance"""
        # Extract pitch contour and look for periodic variations
        valid_pitches = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                valid_pitches.append(pitch)
        
        if len(valid_pitches) < 10:
            return 0.0
        
        # Calculate pitch variation
        pitch_variation = np.std(valid_pitches)
        return float(min(pitch_variation / 100.0, 1.0))  # Normalize
    
    def _detect_breath_sounds(self, y: np.ndarray, sr: int) -> float:
        """Detect breath sounds (high frequency noise)"""
        # Look for noise-like patterns in high frequencies
        stft = librosa.stft(y)
        high_freq_noise = np.mean(np.std(np.abs(stft[int(len(stft) * 0.8):]), axis=0))
        return float(min(high_freq_noise * 10, 1.0))  # Normalize
    
    def _detect_chord_changes(self, y: np.ndarray, sr: int) -> int:
        """Detect chord changes in harmonic content"""
        # Simplified chord change detection using chroma
        chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=1024)
        
        # Look for significant changes in chroma
        chroma_diff = np.diff(chroma, axis=1)
        chord_changes = np.sum(np.linalg.norm(chroma_diff, axis=0) > 0.5)
        
        return int(chord_changes)
    
    def _detect_sustained_notes(self, y: np.ndarray, sr: int) -> float:
        """Detect sustained notes vs. short notes"""
        # Calculate note sustain based on energy consistency
        rms_energy = librosa.feature.rms(y=y, hop_length=512)[0]
        
        # Measure energy stability (less variation = more sustained)
        energy_stability = 1.0 - (np.std(rms_energy) / (np.mean(rms_energy) + 1e-10))
        return float(max(0.0, min(1.0, energy_stability)))
    
    async def _prepare_stem_bark_training_data(
        self,
        stem_path: Path,
        stem_type: str,
        bpm: float,
        key: str,
        duration: float,
        flamingo_analysis: Dict[str, Any],
        technical_features: Dict[str, Any],
        spectral_features: Dict[str, Any],
        psychoacoustic_features: Dict[str, Any],
        stem_characteristics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare Bark training data specifically for individual stems"""
        try:
            logger.info(f"Preparing Bark training data for {stem_type} stem...")
            
            # Create stem-specific description
            description_parts = []
            
            # Basic stem information
            description_parts.append(f"This is a {duration:.1f} second {stem_type} stem")
            
            # Add musical context
            if bpm and bpm > 0:
                tempo_desc = self._describe_tempo(bpm)
                description_parts.append(f"at {tempo_desc} tempo ({bpm:.0f} BPM)")
            
            if key and key != "unknown":
                description_parts.append(f"in {key}")
            
            # Add stem-specific characteristics
            if stem_characteristics and "stem_specific_features" in stem_characteristics:
                stem_features = stem_characteristics["stem_specific_features"]
                
                if stem_type.lower() == "drums":
                    if stem_features.get("kick_drum_presence", 0) > 0.1:
                        description_parts.append("with prominent kick drum")
                    if stem_features.get("snare_presence", 0) > 0.1:
                        description_parts.append("including snare hits")
                    if stem_features.get("hihat_presence", 0) > 0.1:
                        description_parts.append("and hi-hat patterns")
                
                elif stem_type.lower() == "bass":
                    freq_range = stem_features.get("fundamental_frequency_range", [0, 0])
                    if freq_range[1] > freq_range[0]:
                        description_parts.append(f"with fundamental frequencies from {freq_range[0]:.0f} to {freq_range[1]:.0f} Hz")
                    if stem_features.get("sub_bass_presence", 0) > 0.1:
                        description_parts.append("including sub-bass content")
                
                elif stem_type.lower() == "vocals":
                    vocal_range = stem_features.get("vocal_range_hz", [0, 0])
                    if vocal_range[1] > vocal_range[0]:
                        description_parts.append(f"with vocal range from {vocal_range[0]:.0f} to {vocal_range[1]:.0f} Hz")
                    if stem_features.get("vibrato_presence", 0) > 0.3:
                        description_parts.append("featuring vibrato")
                
                elif stem_type.lower() in ["other", "guitar", "keys", "synth"]:
                    harmonic_ratio = stem_features.get("harmonic_ratio", 0)
                    if harmonic_ratio > 0.7:
                        description_parts.append("with strong harmonic content")
                    chord_changes = stem_features.get("chord_changes", 0)
                    if chord_changes > 5:
                        description_parts.append(f"featuring {chord_changes} chord changes")
            
            # Add Flamingo insights if available
            if flamingo_analysis:
                if "caption" in flamingo_analysis and flamingo_analysis["caption"]:
                    caption = flamingo_analysis["caption"].get("description", "")
                    if caption and caption != "Analysis unavailable":
                        description_parts.append(f"Detailed audio analysis: {caption}")
                
                if "instruments" in flamingo_analysis and flamingo_analysis["instruments"]:
                    instruments = flamingo_analysis["instruments"].get("instruments", [])
                    if instruments and stem_type.lower() in [inst.lower() for inst in instruments]:
                        description_parts.append(f"confirmed as {stem_type} instrument")
            
            # Create final description
            full_description = ". ".join(description_parts) + "."
            
            # Prepare structured training data for the stem
            training_data = {
                "audio_path": str(stem_path),
                "text_description": full_description,
                "stem_type": stem_type,
                "musical_attributes": {
                    "tempo_bpm": bpm,
                    "key_signature": key,
                    "duration_seconds": duration,
                    "tempo_class": self._classify_tempo(bpm),
                    "key_mode": self._extract_key_mode(key),
                    "stem_role": stem_type.lower()
                },
                "stem_characteristics": stem_characteristics,
                "technical_attributes": {
                    "sample_rate": technical_features.get("sample_rate", 44100),
                    "dynamic_range": technical_features.get("dynamic_range", 0),
                    "peak_level": technical_features.get("peak_level", 0),
                    "rms_level": technical_features.get("rms_level", 0)
                },
                "spectral_attributes": {
                    "brightness": spectral_features.get("spectral_centroid_mean", 0),
                    "spectral_bandwidth": spectral_features.get("spectral_bandwidth_mean", 0),
                    "harmonic_content": spectral_features.get("harmonic_ratio", 0)
                },
                "semantic_attributes": {
                    "flamingo_description": flamingo_analysis.get("caption", {}).get("description", ""),
                    "detected_instruments": flamingo_analysis.get("instruments", {}).get("instruments", []),
                    "audio_quality": flamingo_analysis.get("quality", {}).get("quality_assessment", "")
                },
                "training_metadata": {
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "confidence_scores": self._calculate_training_confidence(flamingo_analysis),
                    "data_source": f"{stem_type}_stem",
                    "recommended_for_training": self._assess_stem_training_suitability(
                        stem_type, technical_features, flamingo_analysis, duration, stem_characteristics
                    )
                }
            }
            
            logger.info(f"Bark training data preparation completed for {stem_type} stem")
            return training_data
            
        except Exception as e:
            logger.error(f"Error preparing stem Bark training data: {str(e)}")
            return {}
    
    def _assess_stem_training_suitability(
        self,
        stem_type: str,
        technical_features: Dict[str, Any],
        flamingo_analysis: Dict[str, Any],
        duration: float,
        stem_characteristics: Dict[str, Any]
    ) -> bool:
        """Assess if the stem is suitable for training Bark"""
        # Duration check (stems can be shorter than full tracks)
        if duration < 1 or duration > 30:
            return False
        
        # Energy check - stem should have sufficient content
        if stem_characteristics and "energy_profile" in stem_characteristics:
            mean_energy = stem_characteristics["energy_profile"].get("mean_energy", 0)
            if mean_energy < 0.001:  # Too quiet/empty
                return False
        
        # Stem-specific checks
        if stem_type.lower() == "vocals":
            # Check for vocal activity
            if stem_characteristics and "stem_specific_features" in stem_characteristics:
                voice_activity = stem_characteristics["stem_specific_features"].get("voice_activity_ratio", 0)
                if voice_activity < 0.1:  # Less than 10% vocal activity
                    return False
        
        elif stem_type.lower() == "drums":
            # Check for rhythmic content
            if stem_characteristics and "stem_specific_features" in stem_characteristics:
                onset_density = stem_characteristics["stem_specific_features"].get("onset_density", 0)
                if onset_density < 0.5:  # Less than 0.5 hits per second
                    return False
        
        # Technical quality check
        dynamic_range = technical_features.get("dynamic_range", 0)
        if dynamic_range < 3:  # Very compressed
            return False
        
        return True

    async def extract_notation(self, stem_path: Path, stem_type: str, sr: int = 22050) -> Dict[str, Any]:
        """
        Extract musical notation from separated stems
        
        Args:
            stem_path: Path to the stem audio file
            stem_type: Type of stem (drums, bass, other/guitar, vocals)
            sr: Sample rate for analysis
            
        Returns:
            Dictionary containing notation data
        """
        if not NOTATION_AVAILABLE:
            logger.warning("Notation libraries not available")
            return {}
            
        try:
            logger.info(f"Extracting notation for {stem_type} stem: {stem_path}")
            
            # Load audio
            y, _ = librosa.load(str(stem_path), sr=sr)
            
            notation_data = {}
            
            if stem_type.lower() == 'drums':
                notation_data = await self._extract_drum_notation(y, sr)
            elif stem_type.lower() == 'bass':
                notation_data = await self._extract_bass_notation(y, sr)
            elif stem_type.lower() in ['other', 'guitar']:
                notation_data = await self._extract_guitar_notation(y, sr)
            elif stem_type.lower() == 'vocals':
                notation_data = await self._extract_vocal_notation(y, sr)
            
            logger.info(f"Notation extraction completed for {stem_type}")
            return notation_data
            
        except Exception as e:
            logger.error(f"Error extracting notation for {stem_type}: {str(e)}", exc_info=True)
            return {}

    async def _extract_drum_notation(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract drum notation using onset detection and pattern analysis"""
        try:
            # Drum onset detection
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=sr, units='time', hop_length=512, backtrack=True
            )
            
            # Extract spectral features for drum classification
            S = np.abs(librosa.stft(y, hop_length=512))
            spectral_centroids = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
            
            # Simple drum classification based on frequency content
            drum_events = []
            for onset_time in onset_frames:
                # Get spectral features around onset
                frame_idx = int(onset_time * sr / 512)
                if frame_idx < len(spectral_centroids):
                    centroid = spectral_centroids[frame_idx]
                    
                    # Basic drum type classification
                    if centroid > 3000:
                        drum_type = "hi-hat"
                    elif centroid > 1000:
                        drum_type = "snare"
                    else:
                        drum_type = "kick"
                    
                    drum_events.append({
                        "time": float(onset_time),
                        "drum_type": drum_type,
                        "velocity": 80  # Default velocity
                    })
            
            return {
                "notation_type": "drums",
                "events": drum_events,
                "total_events": len(drum_events),
                "duration": float(len(y) / sr)
            }
            
        except Exception as e:
            logger.error(f"Error in drum notation extraction: {str(e)}")
            return {}

    async def _extract_bass_notation(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract bass notation using pitch tracking"""
        try:
            # Pitch tracking for bass (fundamental frequency)
            pitches, magnitudes = librosa.piptrack(
                y=y, sr=sr, threshold=0.1, fmin=50, fmax=400
            )
            
            # Extract pitch contour
            pitch_contour = []
            times = librosa.frames_to_time(np.arange(pitches.shape[1]), sr=sr)
            
            for t_idx in range(pitches.shape[1]):
                # Find the pitch with maximum magnitude
                index = magnitudes[:, t_idx].argmax()
                pitch = pitches[index, t_idx]
                
                if pitch > 0:  # Valid pitch detected
                    note_name = librosa.hz_to_note(pitch)
                    pitch_contour.append({
                        "time": float(times[t_idx]),
                        "frequency": float(pitch),
                        "note": note_name,
                        "confidence": float(magnitudes[index, t_idx])
                    })
            
            # Onset detection for note timing
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=sr, units='time', hop_length=512
            )
            
            return {
                "notation_type": "bass",
                "pitch_contour": pitch_contour,
                "onsets": [float(t) for t in onset_frames],
                "total_notes": len(pitch_contour),
                "duration": float(len(y) / sr)
            }
            
        except Exception as e:
            logger.error(f"Error in bass notation extraction: {str(e)}")
            return {}

    async def _extract_guitar_notation(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract guitar notation including chord detection"""
        try:
            # Pitch tracking for guitar (wider frequency range)
            pitches, magnitudes = librosa.piptrack(
                y=y, sr=sr, threshold=0.1, fmin=80, fmax=2000
            )
            
            # Chord detection using chromagram
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            
            # Simple chord detection (basic major/minor triads)
            chord_templates = self._get_chord_templates()
            
            chord_progression = []
            hop_length = 512
            frame_duration = hop_length / sr
            
            for frame_idx in range(chroma.shape[1]):
                frame_chroma = chroma[:, frame_idx]
                
                # Find best matching chord
                best_chord = None
                best_score = 0
                
                for chord_name, template in chord_templates.items():
                    # Correlation between frame chroma and chord template
                    score = np.corrcoef(frame_chroma, template)[0, 1]
                    if not np.isnan(score) and score > best_score:
                        best_score = score
                        best_chord = chord_name
                
                if best_chord and best_score > 0.6:  # Confidence threshold
                    chord_progression.append({
                        "time": float(frame_idx * frame_duration),
                        "chord": best_chord,
                        "confidence": float(best_score)
                    })
            
            # Onset detection
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=sr, units='time', hop_length=512
            )
            
            return {
                "notation_type": "guitar",
                "chord_progression": chord_progression,
                "onsets": [float(t) for t in onset_frames],
                "total_chords": len(chord_progression),
                "duration": float(len(y) / sr)
            }
            
        except Exception as e:
            logger.error(f"Error in guitar notation extraction: {str(e)}")
            return {}

    async def _extract_vocal_notation(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract vocal melody notation"""
        try:
            # Pitch tracking for vocals
            pitches, magnitudes = librosa.piptrack(
                y=y, sr=sr, threshold=0.1, fmin=80, fmax=800
            )
            
            # Extract melodic contour
            melody = []
            times = librosa.frames_to_time(np.arange(pitches.shape[1]), sr=sr)
            
            for t_idx in range(pitches.shape[1]):
                index = magnitudes[:, t_idx].argmax()
                pitch = pitches[index, t_idx]
                
                if pitch > 0:
                    note_name = librosa.hz_to_note(pitch)
                    melody.append({
                        "time": float(times[t_idx]),
                        "frequency": float(pitch),
                        "note": note_name,
                        "confidence": float(magnitudes[index, t_idx])
                    })
            
            return {
                "notation_type": "vocals",
                "melody": melody,
                "total_notes": len(melody),
                "duration": float(len(y) / sr)
            }
            
        except Exception as e:
            logger.error(f"Error in vocal notation extraction: {str(e)}")
            return {}

    def _get_chord_templates(self) -> Dict[str, np.ndarray]:
        """Get basic chord templates for chord recognition"""
        # Basic major and minor chord templates in chromagram format
        # Each template is a 12-dimensional vector representing the chromagram
        templates = {
            'C': np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]),      # C major
            'Dm': np.array([0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0]),     # D minor
            'Em': np.array([0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1]),     # E minor
            'F': np.array([1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0]),      # F major
            'G': np.array([0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1]),      # G major
            'Am': np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0]),     # A minor
            'Bb': np.array([0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]),     # Bb major
        }
        
        # Normalize templates
        for chord in templates:
            templates[chord] = templates[chord] / np.linalg.norm(templates[chord])
        
        return templates
    
    async def generate_enhanced_analysis_report(self, audio_path: Path, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate an enhanced analysis report that combines traditional MIR analysis
        with Audio Flamingo's advanced audio understanding
        """
        try:
            logger.info("Generating enhanced analysis report...")
            
            # Get the flamingo analysis from results
            flamingo_data = analysis_results.get("flamingo_analysis", {})
            
            # Create enhanced report structure
            enhanced_report = {
                "traditional_analysis": {
                    "tempo": {
                        "bpm": analysis_results.get("bpm"),
                        "confidence": "high" if analysis_results.get("bpm") else "low"
                    },
                    "key_signature": {
                        "key": analysis_results.get("key"),
                        "tuning_frequency": analysis_results.get("tuning_frequency")
                    },
                    "structure": {
                        "sections": len(analysis_results.get("sections", [])),
                        "beats": len(analysis_results.get("beats", [])),
                        "chords": len(analysis_results.get("chords", []))
                    },
                    "genre_classification": analysis_results.get("genre_analysis", {})
                },
                "flamingo_insights": flamingo_data,
                "combined_analysis": self._combine_analysis_insights(analysis_results, flamingo_data),
                "confidence_assessment": self._assess_analysis_confidence(analysis_results, flamingo_data)
            }
            
            logger.info("Enhanced analysis report generated successfully")
            return enhanced_report
            
        except Exception as e:
            logger.error(f"Error generating enhanced analysis report: {str(e)}")
            return analysis_results  # Fall back to original results
    
    def _combine_analysis_insights(self, traditional: Dict[str, Any], flamingo: Dict[str, Any]) -> Dict[str, Any]:
        """Combine insights from traditional MIR and Audio Flamingo analysis"""
        combined = {}
        
        # Genre comparison
        traditional_genre = traditional.get("genre_analysis", {}).get("primary_genre", "unknown")
        flamingo_genre = flamingo.get("genre", {}).get("primary_genre", "unknown")
        
        combined["genre_consensus"] = {
            "traditional": traditional_genre,
            "flamingo": flamingo_genre,
            "agreement": traditional_genre.lower() == flamingo_genre.lower(),
            "recommended": flamingo_genre if flamingo_genre != "unknown" else traditional_genre
        }
        
        # Instrumentation insights
        flamingo_instruments = flamingo.get("instruments", {}).get("instruments", [])
        traditional_stems = ["drums", "bass", "other", "vocals"]  # From Demucs
        
        combined["instrumentation"] = {
            "detected_stems": traditional_stems,
            "flamingo_instruments": flamingo_instruments,
            "enhanced_list": list(set(traditional_stems + flamingo_instruments))
        }
        
        # Mood and quality insights (unique to Flamingo)
        combined["audio_characteristics"] = {
            "mood": flamingo.get("mood", {}).get("mood_description", "Not analyzed"),
            "quality_assessment": flamingo.get("quality", {}).get("quality_assessment", "Not analyzed"),
            "description": flamingo.get("caption", {}).get("description", "Not available")
        }
        
        return combined
    
    def _assess_analysis_confidence(self, traditional: Dict[str, Any], flamingo: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the overall confidence of the analysis"""
        confidence = {
            "overall_score": 0.0,
            "component_scores": {}
        }
        
        # Traditional analysis confidence (based on data availability)
        traditional_score = 0.0
        if traditional.get("bpm"):
            traditional_score += 0.2
        if traditional.get("key"):
            traditional_score += 0.2
        if traditional.get("beats"):
            traditional_score += 0.2
        if traditional.get("sections"):
            traditional_score += 0.2
        if traditional.get("chords"):
            traditional_score += 0.2
        
        confidence["component_scores"]["traditional_mir"] = traditional_score
        
        # Flamingo analysis confidence
        flamingo_confidence = flamingo.get("confidence_scores", {}) if isinstance(flamingo, dict) else {}
        flamingo_score = flamingo_confidence.get("overall", 0.0) if flamingo_confidence else 0.0
        
        confidence["component_scores"]["flamingo_analysis"] = flamingo_score
        
        # Combined confidence (weighted average)
        confidence["overall_score"] = (traditional_score * 0.6) + (flamingo_score * 0.4)
        
        # Confidence level description
        if confidence["overall_score"] >= 0.8:
            confidence["level"] = "high"
        elif confidence["overall_score"] >= 0.6:
            confidence["level"] = "medium"
        else:
            confidence["level"] = "low"
        
        return confidence
    
    async def _prepare_bark_training_data(
        self, 
        audio_path: Path, 
        bpm: float, 
        key: str, 
        duration: float,
        flamingo_analysis: Dict[str, Any],
        technical_features: Dict[str, Any],
        psychoacoustic_features: Dict[str, Any],
        spectral_features: Dict[str, Any],
        temporal_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare comprehensive training data for Bark model"""
        try:
            logger.info("Preparing Bark training data...")
            
            # Create comprehensive text description for Bark training
            description_parts = []
            
            # Basic musical information
            description_parts.append(f"This is a {duration:.1f} second audio track")
            
            if bpm and bpm > 0:
                tempo_desc = self._describe_tempo(bpm)
                description_parts.append(f"with a {tempo_desc} tempo of {bpm:.0f} BPM")
            
            if key and key != "unknown":
                description_parts.append(f"in the key of {key}")
            
            # Add Flamingo analysis descriptions
            if flamingo_analysis:
                if "caption" in flamingo_analysis and flamingo_analysis["caption"]:
                    caption = flamingo_analysis["caption"].get("description", "")
                    if caption and caption != "Analysis unavailable":
                        description_parts.append(f"The audio contains: {caption}")
                
                if "genre" in flamingo_analysis and flamingo_analysis["genre"]:
                    genre = flamingo_analysis["genre"].get("primary_genre", "")
                    if genre and genre != "unknown":
                        description_parts.append(f"The musical style is {genre}")
                
                if "mood" in flamingo_analysis and flamingo_analysis["mood"]:
                    mood = flamingo_analysis["mood"].get("mood_description", "")
                    if mood and mood != "Analysis unavailable":
                        description_parts.append(f"The emotional mood is: {mood}")
                
                if "instruments" in flamingo_analysis and flamingo_analysis["instruments"]:
                    instruments = flamingo_analysis["instruments"].get("instruments", [])
                    if instruments:
                        inst_list = ", ".join(instruments[:5])  # Limit to top 5
                        description_parts.append(f"Instruments include: {inst_list}")
            
            # Add technical characteristics
            if technical_features:
                dynamic_range = technical_features.get("dynamic_range", 0)
                if dynamic_range > 0:
                    if dynamic_range > 20:
                        description_parts.append("with high dynamic range")
                    elif dynamic_range < 10:
                        description_parts.append("with compressed dynamics")
            
            # Add spectral characteristics
            if spectral_features:
                brightness = spectral_features.get("spectral_centroid_mean", 0)
                if brightness > 3000:
                    description_parts.append("with bright, high-frequency content")
                elif brightness < 1000:
                    description_parts.append("with warm, low-frequency emphasis")
            
            # Create final description
            full_description = ". ".join(description_parts) + "."
            
            # Prepare structured training data
            training_data = {
                "audio_path": str(audio_path),
                "text_description": full_description,
                "musical_attributes": {
                    "tempo_bpm": bpm,
                    "key_signature": key,
                    "duration_seconds": duration,
                    "tempo_class": self._classify_tempo(bpm),
                    "key_mode": self._extract_key_mode(key)
                },
                "technical_attributes": {
                    "sample_rate": technical_features.get("sample_rate", 44100),
                    "bit_depth": technical_features.get("bit_depth", 16),
                    "dynamic_range": technical_features.get("dynamic_range", 0),
                    "peak_level": technical_features.get("peak_level", 0),
                    "rms_level": technical_features.get("rms_level", 0)
                },
                "spectral_attributes": {
                    "brightness": spectral_features.get("spectral_centroid_mean", 0),
                    "spectral_bandwidth": spectral_features.get("spectral_bandwidth_mean", 0),
                    "spectral_contrast": spectral_features.get("spectral_contrast_mean", []),
                    "harmonic_content": spectral_features.get("harmonic_ratio", 0)
                },
                "semantic_attributes": {
                    "genre": flamingo_analysis.get("genre", {}).get("primary_genre", "unknown"),
                    "mood": flamingo_analysis.get("mood", {}).get("mood_description", ""),
                    "instruments": flamingo_analysis.get("instruments", {}).get("instruments", []),
                    "vocal_presence": "vocals" in str(flamingo_analysis).lower(),
                    "audio_quality": flamingo_analysis.get("quality", {}).get("quality_assessment", "")
                },
                "training_metadata": {
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "confidence_scores": self._calculate_training_confidence(flamingo_analysis),
                    "data_source": "main_track",
                    "recommended_for_training": self._assess_training_suitability(
                        technical_features, flamingo_analysis, duration
                    )
                }
            }
            
            logger.info("Bark training data preparation completed")
            return training_data
            
        except Exception as e:
            logger.error(f"Error preparing Bark training data: {str(e)}")
            return {}
    
    def _describe_tempo(self, bpm: float) -> str:
        """Convert BPM to descriptive tempo marking"""
        if bpm < 60:
            return "very slow"
        elif bpm < 80:
            return "slow"
        elif bpm < 120:
            return "moderate"
        elif bpm < 140:
            return "fast"
        elif bpm < 180:
            return "very fast"
        else:
            return "extremely fast"
    
    def _classify_tempo(self, bpm: float) -> str:
        """Classify tempo into standard musical categories"""
        if bpm < 60:
            return "largo"
        elif bpm < 80:
            return "adagio"
        elif bpm < 108:
            return "andante"
        elif bpm < 120:
            return "moderato"
        elif bpm < 168:
            return "allegro"
        else:
            return "presto"
    
    def _extract_key_mode(self, key: str) -> str:
        """Extract mode (major/minor) from key signature"""
        if not key or key == "unknown":
            return "unknown"
        return "minor" if "minor" in key.lower() else "major"
    
    def _calculate_training_confidence(self, flamingo_analysis: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence scores for training data quality"""
        confidence_scores = {}
        
        # Extract individual confidence scores from Flamingo analysis
        for category, data in flamingo_analysis.items():
            if isinstance(data, dict) and "confidence" in data:
                confidence_scores[category] = data["confidence"]
        
        # Calculate overall confidence
        if confidence_scores:
            confidence_scores["overall"] = sum(confidence_scores.values()) / len(confidence_scores)
        else:
            confidence_scores["overall"] = 0.5  # Default moderate confidence
        
        return confidence_scores
    
    def _assess_training_suitability(
        self, 
        technical_features: Dict[str, Any], 
        flamingo_analysis: Dict[str, Any],
        duration: float
    ) -> bool:
        """Assess if the audio is suitable for training Bark"""
        # Duration check (Bark works best with 5-30 second clips)
        if duration < 2 or duration > 60:
            return False
        
        # Technical quality check
        dynamic_range = technical_features.get("dynamic_range", 0)
        if dynamic_range < 5:  # Too compressed
            return False
        
        # Confidence check
        confidence_scores = self._calculate_training_confidence(flamingo_analysis)
        overall_confidence = confidence_scores.get("overall", 0)
        if overall_confidence < 0.6:  # Low confidence analysis
            return False
        
        return True
    
    async def export_bark_training_dataset(
        self, 
        analysis_results: Dict[str, Any], 
        stem_analyses: List[Dict[str, Any]], 
        output_dir: Path,
        audio_file_id: str
    ) -> Dict[str, Any]:
        """Export comprehensive Bark training dataset from analysis results"""
        try:
            logger.info("Exporting Bark training dataset...")
            
            # Create output directory structure
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Main track training data
            main_training_data = analysis_results.get("bark_training_data", {})
            
            # Collect all stem training data
            stem_training_data = []
            for stem_analysis in stem_analyses:
                if "bark_training_data" in stem_analysis:
                    stem_training_data.append(stem_analysis["bark_training_data"])
            
            # Create comprehensive training dataset
            training_dataset = {
                "dataset_metadata": {
                    "audio_file_id": audio_file_id,
                    "creation_timestamp": datetime.utcnow().isoformat(),
                    "total_samples": 1 + len(stem_training_data),
                    "main_track_duration": analysis_results.get("duration_seconds", 0),
                    "source_format": "mp3_with_stems",
                    "analysis_version": "1.0"
                },
                "main_track": main_training_data,
                "stems": stem_training_data,
                "combined_features": {
                    "full_track_bpm": analysis_results.get("bpm", 0),
                    "full_track_key": analysis_results.get("key", "unknown"),
                    "instrumentation": [stem.get("stem_type", "") for stem in stem_training_data],
                    "genre": analysis_results.get("flamingo_analysis", {}).get("genre", {}).get("primary_genre", "unknown"),
                    "mood": analysis_results.get("flamingo_analysis", {}).get("mood", {}).get("mood_description", ""),
                    "overall_quality": analysis_results.get("flamingo_analysis", {}).get("quality", {}).get("quality_assessment", "")
                }
            }
            
            # Generate training prompts for different scenarios
            training_prompts = self._generate_bark_training_prompts(training_dataset)
            training_dataset["training_prompts"] = training_prompts
            
            # Save dataset as JSON
            dataset_file = output_dir / f"bark_training_dataset_{audio_file_id}.json"
            with open(dataset_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(training_dataset, f, indent=2, ensure_ascii=False)
            
            # Create training script/instructions
            training_instructions = self._create_bark_training_instructions(training_dataset)
            instructions_file = output_dir / f"training_instructions_{audio_file_id}.md"
            with open(instructions_file, 'w', encoding='utf-8') as f:
                f.write(training_instructions)
            
            # Create manifest file for batch training
            manifest_entry = self._create_training_manifest_entry(training_dataset, audio_file_id)
            
            logger.info(f"Bark training dataset exported to {dataset_file}")
            
            return {
                "dataset_file": str(dataset_file),
                "instructions_file": str(instructions_file),
                "manifest_entry": manifest_entry,
                "total_training_samples": training_dataset["dataset_metadata"]["total_samples"],
                "export_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting Bark training dataset: {str(e)}")
            return {"error": str(e)}
    
    def _generate_bark_training_prompts(self, training_dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate training prompts for Bark model training"""
        prompts = []
        
        # Main track prompt
        main_track = training_dataset.get("main_track", {})
        if main_track:
            main_prompt = {
                "type": "full_track",
                "audio_description": main_track.get("audio_description", ""),
                "style_prompt": main_track.get("style_prompt", ""),
                "technical_prompt": main_track.get("technical_prompt", ""),
                "combined_prompt": f"{main_track.get('audio_description', '')} {main_track.get('style_prompt', '')}".strip(),
                "training_weight": 1.0
            }
            prompts.append(main_prompt)
        
        # Stem prompts
        stems = training_dataset.get("stems", [])
        for i, stem in enumerate(stems):
            stem_prompt = {
                "type": f"stem_{stem.get('stem_type', 'unknown')}",
                "audio_description": stem.get("audio_description", ""),
                "style_prompt": stem.get("style_prompt", ""),
                "technical_prompt": stem.get("technical_prompt", ""),
                "combined_prompt": f"{stem.get('audio_description', '')} {stem.get('style_prompt', '')}".strip(),
                "training_weight": 0.7  # Stems get lower weight
            }
            prompts.append(stem_prompt)
        
        # Create combined prompts for multi-instrument scenarios
        if len(stems) > 1:
            combined_instruments = [stem.get("stem_type", "") for stem in stems]
            combined_prompt = {
                "type": "multi_instrument",
                "audio_description": f"Music with {', '.join(combined_instruments)}",
                "style_prompt": main_track.get("style_prompt", ""),
                "technical_prompt": main_track.get("technical_prompt", ""),
                "combined_prompt": f"Music with {', '.join(combined_instruments)} {main_track.get('style_prompt', '')}".strip(),
                "training_weight": 0.8
            }
            prompts.append(combined_prompt)
        
        return prompts
    
    def _create_bark_training_instructions(self, training_dataset: Dict[str, Any]) -> str:
        """Create training instructions for Bark model"""
        metadata = training_dataset.get("dataset_metadata", {})
        combined_features = training_dataset.get("combined_features", {})
        
        instructions = f"""# Bark Training Dataset Instructions
        
## Dataset Overview
- **Audio File ID**: {metadata.get("audio_file_id", "unknown")}
- **Creation Date**: {metadata.get("creation_timestamp", "unknown")}
- **Total Training Samples**: {metadata.get("total_samples", 0)}
- **Main Track Duration**: {metadata.get("main_track_duration", 0):.2f} seconds
- **Source Format**: {metadata.get("source_format", "unknown")}

## Musical Characteristics
- **BPM**: {combined_features.get("full_track_bpm", "unknown")}
- **Key**: {combined_features.get("full_track_key", "unknown")}
- **Genre**: {combined_features.get("genre", "unknown")}
- **Mood**: {combined_features.get("mood", "unknown")}
- **Instrumentation**: {", ".join(combined_features.get("instrumentation", []))}

## Training Prompts
"""
        
        # Add prompt examples
        training_prompts = training_dataset.get("training_prompts", [])
        for i, prompt in enumerate(training_prompts):
            instructions += f"""
### Prompt {i+1}: {prompt.get("type", "unknown")}
- **Description**: {prompt.get("audio_description", "")}
- **Style**: {prompt.get("style_prompt", "")}
- **Technical**: {prompt.get("technical_prompt", "")}
- **Combined Prompt**: "{prompt.get("combined_prompt", "")}"
- **Training Weight**: {prompt.get("training_weight", 1.0)}
"""
        
        instructions += """
## Training Recommendations
1. Use the combined prompts as primary text inputs for Bark training
2. Apply training weights to balance full track vs. stem learning
3. Consider the technical prompts for fine-tuning audio characteristics
4. Use the style prompts to maintain genre consistency
5. The multi-instrument prompts help with generalization

## Usage Notes
- This dataset is optimized for personal use Bark model training
- Audio features have been analyzed for training suitability
- Confidence scores are included to guide training sample selection
"""
        
        return instructions
    
    def _create_training_manifest_entry(self, training_dataset: Dict[str, Any], audio_file_id: str) -> Dict[str, Any]:
        """Create manifest entry for batch training scenarios"""
        metadata = training_dataset.get("dataset_metadata", {})
        combined_features = training_dataset.get("combined_features", {})
        
        manifest_entry = {
            "audio_id": audio_file_id,
            "dataset_file": f"bark_training_dataset_{audio_file_id}.json",
            "instructions_file": f"training_instructions_{audio_file_id}.md",
            "training_samples": metadata.get("total_samples", 0),
            "duration_seconds": metadata.get("main_track_duration", 0),
            "genre": combined_features.get("genre", "unknown"),
            "bpm": combined_features.get("full_track_bpm", 0),
            "key": combined_features.get("full_track_key", "unknown"),
            "instrumentation": combined_features.get("instrumentation", []),
            "quality_score": combined_features.get("overall_quality", ""),
            "creation_timestamp": metadata.get("creation_timestamp", ""),
            "ready_for_training": True
        }
        
        return manifest_entry
    
    async def analyze_and_export_bark_dataset(
        self, 
        audio_path: Path, 
        stems_dir: Path,
        output_dir: Path,
        audio_file_id: str
    ) -> Dict[str, Any]:
        """Complete analysis pipeline: main track + stems + Bark dataset export with MAXIMUM detail"""
        try:
            logger.info(f"Starting ultra-comprehensive analysis for Bark training: {audio_file_id}")
            
            # Analyze main track with standard analysis
            logger.info("Analyzing main audio track...")
            main_analysis = await self.analyze_music(audio_path)
            
            # Extract ULTRA-DETAILED features for main track
            logger.info("Extracting ultra-detailed features for maximum Bark training quality...")
            ultra_detailed_features = await self.extract_ultra_detailed_bark_features(audio_path)
            
            # Merge ultra-detailed features into main analysis
            main_analysis["ultra_detailed_features"] = ultra_detailed_features
            
            # Analyze stems if available
            stem_analyses = []
            if stems_dir.exists():
                logger.info("Analyzing individual stems with ultra-detailed extraction...")
                
                # Common stem file patterns
                stem_patterns = [
                    ("drums", ["*drums*", "*kick*", "*snare*", "*hihat*"]),
                    ("bass", ["*bass*", "*sub*"]),  
                    ("vocals", ["*vocal*", "*voice*", "*singing*"]),
                    ("other", ["*other*", "*harmonic*", "*melody*", "*piano*", "*guitar*"])
                ]
                
                for stem_type, patterns in stem_patterns:
                    stem_files = []
                    for pattern in patterns:
                        stem_files.extend(stems_dir.glob(f"{pattern}.wav"))
                        stem_files.extend(stems_dir.glob(f"{pattern}.mp3"))
                    
                    if stem_files:
                        # Use the first matching file for each stem type
                        stem_file = stem_files[0]
                        logger.info(f"Analyzing {stem_type} stem with ultra-detailed extraction: {stem_file.name}")
                        
                        try:
                            # Standard stem analysis
                            stem_analysis = await self.analyze_stem_comprehensive(
                                stem_file, stem_type
                            )
                            
                            # Add ultra-detailed features for this stem
                            stem_ultra_features = await self.extract_ultra_detailed_bark_features(
                                stem_file, stem_type=stem_type
                            )
                            stem_analysis["ultra_detailed_features"] = stem_ultra_features
                            
                            stem_analyses.append(stem_analysis)
                            logger.info(f"{stem_type.capitalize()} stem ultra-detailed analysis completed")
                        except Exception as e:
                            logger.warning(f"Failed to analyze {stem_type} stem: {str(e)}")
            
            # Export comprehensive Bark training dataset with all ultra-detailed features
            logger.info("Exporting ultra-comprehensive Bark training dataset...")
            export_result = await self.export_bark_training_dataset(
                main_analysis, stem_analyses, output_dir, audio_file_id
            )
            
            # Combine all results
            pipeline_result = {
                "audio_file_id": audio_file_id,
                "main_analysis": main_analysis,
                "stem_analyses": stem_analyses,
                "export_result": export_result,
                "pipeline_success": "error" not in export_result,
                "total_training_samples": len(stem_analyses) + 1,
                "ultra_detailed_features_included": True,
                "feature_extraction_level": "maximum",
                "completion_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Ultra-comprehensive analysis pipeline completed for {audio_file_id}")
            logger.info(f"Generated {pipeline_result['total_training_samples']} training samples with maximum detail")
            
            return pipeline_result
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis pipeline: {str(e)}")
            return {
                "error": str(e),
                "audio_file_id": audio_file_id,
                "pipeline_success": False
            }
    
    async def extract_ultra_detailed_bark_features(
        self,
        audio_path: Path,
        stem_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract MAXIMUM possible detail from audio for Bark training.
        This is the most comprehensive analysis available.
        """
        try:
            logger.info(f"Starting ultra-detailed feature extraction for {audio_path.name}")
            
            # Load audio at multiple sample rates for different analyses
            y_standard, sr_standard = librosa.load(audio_path, sr=22050, mono=True)
            y_high, sr_high = librosa.load(audio_path, sr=44100, mono=True)
            
            # Also load in stereo if available for spatial analysis
            y_stereo, sr_stereo = librosa.load(audio_path, sr=44100, mono=False)
            
            ultra_features = {
                "basic_properties": self._extract_basic_audio_properties(y_high, sr_high, y_stereo),
                "spectral_detailed": self._extract_detailed_spectral_features(y_standard, sr_standard),
                "temporal_detailed": self._extract_detailed_temporal_features(y_standard, sr_standard),
                "harmonic_detailed": self._extract_detailed_harmonic_features(y_standard, sr_standard),
                "rhythmic_detailed": self._extract_detailed_rhythmic_features(y_standard, sr_standard),
                "timbral_detailed": self._extract_detailed_timbral_features(y_standard, sr_standard),
                "psychoacoustic_detailed": self._extract_detailed_psychoacoustic_features(y_high, sr_high),
                "spatial_detailed": self._extract_spatial_features(y_stereo) if y_stereo.ndim > 1 else {},
                "transient_detailed": self._extract_transient_characteristics(y_standard, sr_standard),
                "frequency_bands_detailed": self._extract_frequency_band_analysis(y_standard, sr_standard)
            }
            
            logger.info("Ultra-detailed feature extraction completed")
            return ultra_features
            
        except Exception as e:
            logger.error(f"Error in ultra-detailed feature extraction: {str(e)}")
            return {}
    
    def _extract_basic_audio_properties(
        self, 
        y: np.ndarray, 
        sr: int, 
        y_stereo: np.ndarray
    ) -> Dict[str, Any]:
        """Extract comprehensive basic audio properties"""
        duration = len(y) / sr
        
        # RMS and dynamic range
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        dynamic_range_db = 20 * np.log10(np.max(rms) / (np.min(rms) + 1e-10))
        
        # Peak and loudness
        peak_amplitude = np.max(np.abs(y))
        peak_db = 20 * np.log10(peak_amplitude + 1e-10)
        
        # Crest factor (peak to RMS ratio)
        crest_factor = peak_amplitude / (np.mean(rms) + 1e-10)
        
        # Stereo analysis
        stereo_info = {}
        if y_stereo.ndim > 1 and y_stereo.shape[0] == 2:
            left, right = y_stereo[0], y_stereo[1]
            stereo_correlation = np.corrcoef(left, right)[0, 1]
            stereo_width = 1.0 - abs(stereo_correlation)
            
            # Channel balance
            left_energy = np.mean(left ** 2)
            right_energy = np.mean(right ** 2)
            balance = (right_energy - left_energy) / (right_energy + left_energy + 1e-10)
            
            stereo_info = {
                "stereo_correlation": float(stereo_correlation),
                "stereo_width": float(stereo_width),
                "channel_balance": float(balance),
                "left_rms_db": float(20 * np.log10(np.sqrt(left_energy) + 1e-10)),
                "right_rms_db": float(20 * np.log10(np.sqrt(right_energy) + 1e-10)),
                "is_mono_compatible": bool(abs(stereo_correlation) > 0.95)
            }
        
        return {
            "duration_seconds": float(duration),
            "sample_rate": int(sr),
            "total_samples": int(len(y)),
            "peak_amplitude": float(peak_amplitude),
            "peak_db": float(peak_db),
            "rms_mean": float(np.mean(rms)),
            "rms_std": float(np.std(rms)),
            "dynamic_range_db": float(dynamic_range_db),
            "crest_factor_db": float(20 * np.log10(crest_factor)),
            "energy_total": float(np.sum(y ** 2)),
            "zero_crossing_rate_mean": float(np.mean(librosa.zero_crossings(y))),
            **stereo_info
        }
    
    def _extract_detailed_spectral_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract ultra-detailed spectral characteristics"""
        
        # Compute STFT
        stft = librosa.stft(y, n_fft=2048, hop_length=512)
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # Basic spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        spectral_flatness = librosa.feature.spectral_flatness(y=y)[0]
        
        # Advanced spectral features
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr, n_bands=6)
        
        # Spectral flux (measure of spectral change)
        spectral_flux = np.sqrt(np.sum(np.diff(magnitude, axis=1) ** 2, axis=0))
        
        # Spectral slope (tilt of spectrum)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        spectral_slope = []
        for i in range(magnitude.shape[1]):
            if np.sum(magnitude[:, i]) > 0:
                slope = np.polyfit(freqs, magnitude[:, i], 1)[0]
                spectral_slope.append(slope)
        
        # Harmonic vs noise ratio
        harmonic, percussive = librosa.effects.hpss(y)
        harmonic_energy = np.sum(harmonic ** 2)
        percussive_energy = np.sum(percussive ** 2)
        hnr = harmonic_energy / (percussive_energy + 1e-10)
        
        return {
            "spectral_centroid": {
                "mean_hz": float(np.mean(spectral_centroids)),
                "std_hz": float(np.std(spectral_centroids)),
                "min_hz": float(np.min(spectral_centroids)),
                "max_hz": float(np.max(spectral_centroids)),
                "range_hz": float(np.ptp(spectral_centroids))
            },
            "spectral_rolloff": {
                "mean_hz": float(np.mean(spectral_rolloff)),
                "std_hz": float(np.std(spectral_rolloff))
            },
            "spectral_bandwidth": {
                "mean_hz": float(np.mean(spectral_bandwidth)),
                "std_hz": float(np.std(spectral_bandwidth))
            },
            "spectral_flatness": {
                "mean": float(np.mean(spectral_flatness)),
                "std": float(np.std(spectral_flatness)),
                "tonality_coefficient": float(1.0 - np.mean(spectral_flatness))
            },
            "spectral_contrast": {
                f"band_{i}_contrast": float(np.mean(spectral_contrast[i]))
                for i in range(spectral_contrast.shape[0])
            },
            "spectral_flux": {
                "mean": float(np.mean(spectral_flux)),
                "std": float(np.std(spectral_flux)),
                "max": float(np.max(spectral_flux))
            },
            "spectral_slope": {
                "mean": float(np.mean(spectral_slope)) if spectral_slope else 0.0,
                "std": float(np.std(spectral_slope)) if spectral_slope else 0.0
            },
            "harmonic_to_noise_ratio_db": float(10 * np.log10(hnr)),
            "mfcc_coefficients": {
                f"mfcc_{i}": {
                    "mean": float(np.mean(mfccs[i])),
                    "std": float(np.std(mfccs[i])),
                    "delta": float(np.mean(np.diff(mfccs[i])))
                }
                for i in range(min(13, mfccs.shape[0]))  # First 13 MFCCs most important
            },
            "spectral_entropy": float(self._calculate_spectral_entropy(magnitude))
        }
    
    def _extract_detailed_temporal_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract comprehensive temporal characteristics"""
        
        # Onset detection with multiple methods
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets_energy = librosa.onset.onset_detect(y=y, sr=sr, units='time')
        onsets_complex = librosa.onset.onset_detect(
            y=y, sr=sr, units='time', hop_length=512, backtrack=True
        )
        
        # Tempo estimation with multiple methods
        tempo_static = librosa.beat.tempo(y=y, sr=sr)[0]
        
        # Beat tracking
        _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units='frames')
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        # Tempogram for rhythm analysis
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        
        # Autocorrelation for periodicity
        autocorr = librosa.autocorrelate(onset_env)
        
        # Attack, decay, sustain, release (ADSR) envelope estimation
        envelope = librosa.onset.onset_strength(y=y, sr=sr)
        envelope_smooth = librosa.util.smooth(envelope, 3)
        
        return {
            "onset_detection": {
                "onset_count": len(onsets_energy),
                "onset_rate_per_second": float(len(onsets_energy) / (len(y) / sr)),
                "onset_strength_mean": float(np.mean(onset_env)),
                "onset_strength_std": float(np.std(onset_env)),
                "onset_strength_max": float(np.max(onset_env)),
                "inter_onset_interval_mean": float(np.mean(np.diff(onsets_energy))) if len(onsets_energy) > 1 else 0.0,
                "inter_onset_interval_std": float(np.std(np.diff(onsets_energy))) if len(onsets_energy) > 1 else 0.0
            },
            "tempo_rhythm": {
                "tempo_bpm": float(tempo_static),
                "beat_count": len(beat_times),
                "beats_per_duration": float(len(beat_times) / (len(y) / sr)),
                "beat_regularity": float(np.std(np.diff(beat_times))) if len(beat_times) > 1 else 0.0,
                "rhythm_complexity": float(np.std(tempogram)),
                "rhythmic_strength": float(np.max(np.mean(tempogram, axis=1)))
            },
            "periodicity": {
                "autocorrelation_peak": float(np.max(autocorr[1:])),  # Skip lag-0
                "periodicity_strength": float(np.std(autocorr)),
                "is_periodic": bool(np.max(autocorr[1:]) > 0.7)
            },
            "envelope_characteristics": {
                "envelope_mean": float(np.mean(envelope_smooth)),
                "envelope_std": float(np.std(envelope_smooth)),
                "envelope_attack_rate": float(np.max(np.diff(envelope_smooth))),
                "envelope_decay_rate": float(np.min(np.diff(envelope_smooth))),
                "envelope_sustain_level": float(np.median(envelope_smooth))
            }
        }
    
    def _extract_detailed_harmonic_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract deep harmonic and pitch information"""
        
        # Harmonic-percussive separation
        y_harmonic, y_percussive = librosa.effects.hpss(y, margin=2.0)
        
        # Chroma features (pitch class profiles)
        chroma_stft = librosa.feature.chroma_stft(y=y_harmonic, sr=sr)
        chroma_cqt = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr)
        chroma_cens = librosa.feature.chroma_cens(y=y_harmonic, sr=sr)
        
        # Tonnetz (tonal centroid features)
        tonnetz = librosa.feature.tonnetz(y=y_harmonic, sr=sr)
        
        # Pitch tracking
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y_harmonic, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr
        )
        
        # Remove NaN values for analysis
        f0_valid = f0[~np.isnan(f0)]
        
        # Harmonic change detection
        harmonic_changes = np.sum(np.abs(np.diff(chroma_stft, axis=1)) > 0.3, axis=0)
        
        return {
            "harmonic_percussive_balance": {
                "harmonic_energy_ratio": float(np.sum(y_harmonic ** 2) / (np.sum(y ** 2) + 1e-10)),
                "percussive_energy_ratio": float(np.sum(y_percussive ** 2) / (np.sum(y ** 2) + 1e-10))
            },
            "pitch_content": {
                "fundamental_frequency_mean_hz": float(np.mean(f0_valid)) if len(f0_valid) > 0 else 0.0,
                "fundamental_frequency_std_hz": float(np.std(f0_valid)) if len(f0_valid) > 0 else 0.0,
                "fundamental_frequency_range_hz": float(np.ptp(f0_valid)) if len(f0_valid) > 0 else 0.0,
                "voiced_ratio": float(np.sum(voiced_flag) / len(voiced_flag)) if len(voiced_flag) > 0 else 0.0,
                "pitch_stability": float(np.mean(voiced_probs[voiced_flag])) if np.any(voiced_flag) else 0.0
            },
            "chroma_features": {
                "chroma_stft_mean": [float(np.mean(chroma_stft[i])) for i in range(12)],
                "chroma_stft_std": [float(np.std(chroma_stft[i])) for i in range(12)],
                "dominant_pitch_class": int(np.argmax(np.mean(chroma_stft, axis=1))),
                "pitch_class_entropy": float(self._calculate_entropy(np.mean(chroma_stft, axis=1)))
            },
            "tonnetz_features": {
                "tonal_centroid_1": float(np.mean(tonnetz[0])),
                "tonal_centroid_2": float(np.mean(tonnetz[1])),
                "harmonic_change_rate": float(np.mean(harmonic_changes))
            }
        }
    
    def _extract_detailed_rhythmic_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract comprehensive rhythmic characteristics"""
        
        # Onset strength envelope
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        # Tempogram with multiple hop sizes
        tempogram_fine = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr, hop_length=256)
        tempogram_coarse = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr, hop_length=1024)
        
        # Rhythm patterns
        rhythm_pattern = librosa.util.sync(onset_env[np.newaxis, :], range(0, len(onset_env), 8))[0]
        
        # Pulse clarity
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr)
        
        return {
            "rhythm_patterns": {
                "pattern_complexity": float(np.std(rhythm_pattern)),
                "pattern_repetition": float(np.corrcoef(rhythm_pattern[:-1], rhythm_pattern[1:])[0, 1]) if len(rhythm_pattern) > 1 else 0.0
            },
            "pulse_characteristics": {
                "pulse_clarity": float(np.max(pulse)),
                "pulse_stability": float(1.0 / (np.std(pulse) + 1e-10))
            },
            "tempogram_analysis": {
                "tempo_variation": float(np.std(np.argmax(tempogram_fine, axis=0))),
                "rhythm_consistency": float(1.0 / (np.std(tempogram_coarse) + 1e-10))
            }
        }
    
    def _extract_detailed_timbral_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract comprehensive timbral characteristics"""
        
        # Mel spectrogram
        mel_spec = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
        
        # Mel-frequency cepstral coefficients (extended)
        mfcc_full = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
        
        # Delta and delta-delta MFCCs
        mfcc_delta = librosa.feature.delta(mfcc_full)
        mfcc_delta2 = librosa.feature.delta(mfcc_full, order=2)
        
        # Spectral features
        spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        spec_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        
        # Timbre brightness
        brightness = np.mean(spec_cent) / (sr / 2)
        
        # Timbre roughness (high-frequency content variation)
        roughness = np.std(mel_spec_db[-20:, :])  # Last 20 mel bands
        
        return {
            "timbral_brightness": {
                "brightness_ratio": float(brightness),
                "brightness_variation": float(np.std(spec_cent) / (np.mean(spec_cent) + 1e-10))
            },
            "timbral_texture": {
                "roughness": float(roughness),
                "smoothness": float(1.0 / (roughness + 1.0))
            },
            "mel_features": {
                "mel_energy_distribution": [float(np.mean(mel_spec_db[i*16:(i+1)*16])) for i in range(8)],
                "mel_temporal_variation": float(np.mean(np.std(mel_spec_db, axis=1)))
            },
            "mfcc_dynamics": {
                "mfcc_delta_energy": float(np.mean(np.abs(mfcc_delta))),
                "mfcc_acceleration": float(np.mean(np.abs(mfcc_delta2))),
                "timbre_change_rate": float(np.mean(np.sqrt(np.sum(mfcc_delta ** 2, axis=0))))
            }
        }
    
    def _extract_detailed_psychoacoustic_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract psychoacoustic perceptual features"""
        
        # Loudness estimation (A-weighting approximation)
        # Apply A-weighting filter
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        a_weighting = self._a_weighting_filter(freqs)
        
        stft = librosa.stft(y, n_fft=2048)
        magnitude = np.abs(stft)
        weighted_magnitude = magnitude * a_weighting[:, np.newaxis]
        loudness_curve = np.sum(weighted_magnitude, axis=0)
        
        # Sharpness (based on high-frequency emphasis)
        sharpness = np.sum(magnitude[len(freqs)//2:, :]) / (np.sum(magnitude) + 1e-10)
        
        # Roughness estimate (amplitude modulation in critical bands)
        mel_spec = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=40)
        roughness_per_band = np.std(np.diff(mel_spec, axis=1), axis=1)
        
        return {
            "perceived_loudness": {
                "loudness_mean": float(np.mean(loudness_curve)),
                "loudness_std": float(np.std(loudness_curve)),
                "loudness_range_lu": float(20 * np.log10(np.max(loudness_curve) / (np.min(loudness_curve) + 1e-10)))
            },
            "sharpness": {
                "sharpness_coefficient": float(sharpness),
                "perceived_brightness": "bright" if sharpness > 0.3 else "warm"
            },
            "roughness": {
                "overall_roughness": float(np.mean(roughness_per_band)),
                "roughness_variation": float(np.std(roughness_per_band))
            }
        }
    
    def _extract_spatial_features(self, y_stereo: np.ndarray) -> Dict[str, Any]:
        """Extract spatial audio characteristics from stereo signal"""
        
        if y_stereo.ndim != 2 or y_stereo.shape[0] != 2:
            return {}
        
        left, right = y_stereo[0], y_stereo[1]
        
        # Mid-side encoding
        mid = (left + right) / 2
        side = (left - right) / 2
        
        # Stereo width
        mid_energy = np.sum(mid ** 2)
        side_energy = np.sum(side ** 2)
        stereo_width = side_energy / (mid_energy + side_energy + 1e-10)
        
        # Phase coherence
        phase_coherence = np.mean(np.sign(left) == np.sign(right))
        
        # Spatial distribution over time
        stft_left = librosa.stft(left)
        stft_right = librosa.stft(right)
        
        mag_left = np.abs(stft_left)
        mag_right = np.abs(stft_right)
        
        spatial_balance = (mag_right - mag_left) / (mag_right + mag_left + 1e-10)
        
        return {
            "stereo_width": {
                "width_ratio": float(stereo_width),
                "perceived_width": "wide" if stereo_width > 0.5 else "narrow"
            },
            "phase_coherence": {
                "coherence_ratio": float(phase_coherence),
                "mono_compatibility": "good" if phase_coherence > 0.8 else "poor"
            },
            "spatial_balance": {
                "mean_balance": float(np.mean(spatial_balance)),
                "balance_variation": float(np.std(spatial_balance))
            },
            "mid_side_energy": {
                "mid_energy_ratio": float(mid_energy / (mid_energy + side_energy + 1e-10)),
                "side_energy_ratio": float(side_energy / (mid_energy + side_energy + 1e-10))
            }
        }
    
    def _extract_transient_characteristics(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract detailed transient and attack characteristics"""
        
        # Onset strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units='time')
        
        # Analyze transients around each onset
        attack_times = []
        transient_energies = []
        
        for onset_time in onsets[:min(len(onsets), 100)]:  # Analyze first 100 onsets
            onset_sample = int(onset_time * sr)
            
            if onset_sample + int(0.05 * sr) < len(y):  # 50ms window
                transient = y[onset_sample:onset_sample + int(0.05 * sr)]
                
                # Attack time (time to 90% of peak)
                peak_val = np.max(np.abs(transient))
                attack_threshold = 0.9 * peak_val
                attack_idx = np.where(np.abs(transient) >= attack_threshold)[0]
                
                if len(attack_idx) > 0:
                    attack_times.append(attack_idx[0] / sr * 1000)  # Convert to ms
                
                # Transient energy
                transient_energies.append(np.sum(transient ** 2))
        
        return {
            "transient_density": {
                "transients_per_second": float(len(onsets) / (len(y) / sr)),
                "total_transient_count": len(onsets)
            },
            "attack_characteristics": {
                "mean_attack_time_ms": float(np.mean(attack_times)) if attack_times else 0.0,
                "attack_time_std_ms": float(np.std(attack_times)) if attack_times else 0.0,
                "fastest_attack_ms": float(np.min(attack_times)) if attack_times else 0.0,
                "slowest_attack_ms": float(np.max(attack_times)) if attack_times else 0.0
            },
            "transient_energy": {
                "mean_transient_energy": float(np.mean(transient_energies)) if transient_energies else 0.0,
                "transient_energy_variation": float(np.std(transient_energies)) if transient_energies else 0.0
            }
        }
    
    def _extract_frequency_band_analysis(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract detailed frequency band characteristics"""
        
        stft = librosa.stft(y, n_fft=4096, hop_length=1024)
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
        
        # Define frequency bands (extended)
        bands = {
            "sub_bass": (20, 60),
            "bass": (60, 250),
            "low_mid": (250, 500),
            "mid": (500, 2000),
            "high_mid": (2000, 4000),
            "presence": (4000, 6000),
            "brilliance": (6000, 10000),
            "air": (10000, 20000)
        }
        
        band_analysis = {}
        
        for band_name, (low_freq, high_freq) in bands.items():
            band_mask = (freqs >= low_freq) & (freqs < high_freq)
            band_magnitude = magnitude[band_mask, :]
            
            if band_magnitude.size > 0:
                band_analysis[band_name] = {
                    "mean_energy": float(np.mean(band_magnitude)),
                    "max_energy": float(np.max(band_magnitude)),
                    "energy_variation": float(np.std(band_magnitude)),
                    "spectral_centroid_hz": float(np.sum(freqs[band_mask, np.newaxis] * band_magnitude) / (np.sum(band_magnitude) + 1e-10)),
                    "energy_ratio": float(np.sum(band_magnitude) / (np.sum(magnitude) + 1e-10))
                }
        
        # Band balance analysis
        total_energy = np.sum(magnitude)
        low_energy = sum(band_analysis[b]["mean_energy"] for b in ["sub_bass", "bass", "low_mid"])
        mid_energy = sum(band_analysis[b]["mean_energy"] for b in ["mid", "high_mid"])
        high_energy = sum(band_analysis[b]["mean_energy"] for b in ["presence", "brilliance", "air"])
        
        return {
            "frequency_bands": band_analysis,
            "band_balance": {
                "low_ratio": float(low_energy / total_energy) if total_energy > 0 else 0.0,
                "mid_ratio": float(mid_energy / total_energy) if total_energy > 0 else 0.0,
                "high_ratio": float(high_energy / total_energy) if total_energy > 0 else 0.0,
                "balance_description": self._describe_frequency_balance(low_energy, mid_energy, high_energy)
            }
        }
    
    # Helper methods for ultra-detailed extraction
    
    def _calculate_spectral_entropy(self, magnitude: np.ndarray) -> float:
        """Calculate spectral entropy"""
        magnitude_norm = magnitude / (np.sum(magnitude, axis=0, keepdims=True) + 1e-10)
        entropy = -np.sum(magnitude_norm * np.log2(magnitude_norm + 1e-10), axis=0)
        return np.mean(entropy)
    
    def _calculate_entropy(self, distribution: np.ndarray) -> float:
        """Calculate entropy of a probability distribution"""
        distribution_norm = distribution / (np.sum(distribution) + 1e-10)
        return -np.sum(distribution_norm * np.log2(distribution_norm + 1e-10))
    
    def _a_weighting_filter(self, freqs: np.ndarray) -> np.ndarray:
        """Approximate A-weighting filter for loudness"""
        # Simplified A-weighting approximation
        f2 = freqs ** 2
        weighting = (12194 ** 2 * f2 ** 2) / (
            (f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194 ** 2)
        )
        return weighting / np.max(weighting + 1e-10)
    
    def _describe_frequency_balance(self, low: float, mid: float, high: float) -> str:
        """Describe frequency balance in natural language"""
        total = low + mid + high + 1e-10
        low_ratio = low / total
        mid_ratio = mid / total
        high_ratio = high / total
        
        if low_ratio > 0.45:
            return "bass-heavy with warm low-end emphasis"
        elif high_ratio > 0.45:
            return "bright with pronounced high-frequency content"
        elif mid_ratio > 0.50:
            return "mid-focused with clear vocal/instrumental range"
        elif abs(low_ratio - high_ratio) < 0.1:
            return "balanced with even frequency distribution"
        else:
            return "mixed frequency character"
