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
            
            # Extract tempo (BPM)
            bpm = await self._extract_tempo(y, sr)
            
            # Extract key and tuning
            key, tuning = await self._extract_key_tuning(y, sr)
            
            # Extract beats
            logger.info("Starting beat extraction...")
            beats = await self._extract_beats(y, sr)
            logger.info(f"Beat extraction complete: {len(beats)} beats extracted")
            
            # Extract sections (structural segmentation)
            logger.info("Starting section extraction...")
            sections = await self._extract_sections(y, sr)
            logger.info(f"Section extraction complete: {len(sections)} sections extracted")
            
            # Extract chords
            logger.info("Starting chord extraction...")
            chords = await self._extract_chords(y, sr)
            logger.info(f"Chord extraction complete: {len(chords)} chords extracted")
            
            # Add music theory analysis
            logger.info("Starting music theory analysis...")
            harmonic_analysis = self.theory_analyzer.analyze_harmonic_progression(
                chords, key, bpm
            )
            logger.info(f"Harmonic analysis complete: {len(harmonic_analysis)} features")
            
            rhythmic_analysis = self.theory_analyzer.analyze_rhythmic_complexity(
                beats, bpm, duration
            )
            logger.info(f"Rhythmic analysis complete: complexity={rhythmic_analysis.get('complexity_score', 0):.2f}")
            
            # Detect genre based on musical characteristics
            instrumentation = ["drums", "bass", "other", "vocals"]  # From Demucs stems
            genre_analysis = self.theory_analyzer.detect_genre_conventions(
                harmonic_analysis, rhythmic_analysis, instrumentation
            )
            logger.info(f"Genre analysis complete: primary={genre_analysis.get('primary_genre', 'unknown')}")
            
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
                "genre_analysis": genre_analysis
            }
            
            logger.info(f"Analysis complete: BPM={bpm}, Key={key}, Tuning={tuning}Hz")
            return results
            
        except Exception as e:
            logger.error(f"Error in music analysis: {str(e)}", exc_info=True)
            raise
    
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
