"""
Music Theory Analysis Module

Provides deep musical understanding including:
- Harmonic progression analysis (Roman numerals, functional harmony)
- Rhythmic complexity metrics (syncopation, polyrhythm)
- Genre convention detection
- Voice leading analysis
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class ChordQuality(Enum):
    """Chord quality types"""
    MAJOR = "major"
    MINOR = "minor"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    DOMINANT7 = "dominant7"
    MAJOR7 = "major7"
    MINOR7 = "minor7"
    DIMINISHED7 = "diminished7"


class HarmonicFunction(Enum):
    """Functional harmony categories"""
    TONIC = "tonic"
    SUBDOMINANT = "subdominant"
    DOMINANT = "dominant"
    TONIC_SUBSTITUTE = "tonic_substitute"
    SUBDOMINANT_SUBSTITUTE = "subdominant_substitute"
    DOMINANT_SUBSTITUTE = "dominant_substitute"


class MusicTheoryAnalyzer:
    """
    Analyzes music using formal music theory concepts
    """
    
    # Circle of fifths (for key relationships)
    CIRCLE_OF_FIFTHS = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F']
    
    # Note names
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # Roman numerals for scale degrees
    ROMAN_NUMERALS_MAJOR = ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°']
    ROMAN_NUMERALS_MINOR = ['i', 'ii°', 'III', 'iv', 'v', 'VI', 'VII']
    
    # Functional harmony mapping (major key)
    MAJOR_FUNCTIONS = {
        'I': HarmonicFunction.TONIC,
        'ii': HarmonicFunction.SUBDOMINANT,
        'iii': HarmonicFunction.TONIC_SUBSTITUTE,
        'IV': HarmonicFunction.SUBDOMINANT,
        'V': HarmonicFunction.DOMINANT,
        'vi': HarmonicFunction.TONIC_SUBSTITUTE,
        'vii°': HarmonicFunction.DOMINANT_SUBSTITUTE
    }
    
    def __init__(self):
        self.genre_patterns = self._load_genre_patterns()
    
    def analyze_harmonic_progression(
        self,
        chords: List[Dict[str, Any]],
        key: str,
        bpm: float
    ) -> Dict[str, Any]:
        """
        Analyze harmonic progression with music theory
        
        Args:
            chords: List of chord dictionaries from analysis
            key: Musical key (e.g., "C major", "A minor")
            bpm: Tempo in beats per minute
            
        Returns:
            Dictionary with harmonic analysis
        """
        try:
            if not chords:
                return {}
            
            # Parse key
            key_root, key_mode = self._parse_key(key)
            
            # Convert chords to Roman numerals
            roman_numerals = self._chords_to_roman_numerals(chords, key_root, key_mode)
            
            # Analyze functional harmony
            functions = self._analyze_functional_harmony(roman_numerals, key_mode)
            
            # Detect common patterns
            patterns = self._detect_chord_patterns(roman_numerals)
            
            # Calculate harmonic rhythm (chord change frequency)
            harmonic_rhythm = self._calculate_harmonic_rhythm(chords, bpm)
            
            # Detect cadences
            cadences = self._detect_cadences(roman_numerals, chords)
            
            # Analyze voice leading
            voice_leading = self._analyze_voice_leading(chords, key_root)
            
            # Detect modulations (key changes)
            modulations = self._detect_modulations(chords, key_root, key_mode)
            
            return {
                "key": key,
                "key_root": key_root,
                "key_mode": key_mode,
                "roman_numerals": roman_numerals,
                "functional_harmony": functions,
                "common_patterns": patterns,
                "harmonic_rhythm": harmonic_rhythm,
                "cadences": cadences,
                "voice_leading_quality": voice_leading,
                "modulations": modulations,
                "progression_complexity": self._calculate_progression_complexity(roman_numerals)
            }
            
        except Exception as e:
            logger.error(f"Error in harmonic analysis: {e}")
            return {}
    
    def analyze_rhythmic_complexity(
        self,
        beats: List[Dict[str, Any]],
        bpm: float,
        duration: float
    ) -> Dict[str, Any]:
        """
        Analyze rhythmic complexity and patterns
        
        Args:
            beats: List of beat dictionaries
            bpm: Tempo
            duration: Total duration in seconds
            
        Returns:
            Rhythmic complexity metrics
        """
        try:
            if not beats:
                return {}
            
            # Calculate syncopation index
            syncopation = self._calculate_syncopation(beats, bpm)
            
            # Detect time signature
            time_signature = self._detect_time_signature(beats, bpm)
            
            # Calculate note density
            note_density = len(beats) / duration if duration > 0 else 0
            
            # Detect polyrhythms
            polyrhythms = self._detect_polyrhythms(beats)
            
            # Analyze metric hierarchy (downbeats vs upbeats)
            metric_hierarchy = self._analyze_metric_hierarchy(beats, time_signature)
            
            # Calculate rhythmic complexity score
            complexity_score = self._calculate_rhythmic_complexity(
                syncopation, note_density, polyrhythms, metric_hierarchy
            )
            
            return {
                "syncopation_index": syncopation,
                "time_signature": time_signature,
                "note_density": note_density,
                "polyrhythms_detected": polyrhythms,
                "metric_hierarchy": metric_hierarchy,
                "complexity_score": complexity_score,
                "bpm": bpm,
                "total_beats": len(beats)
            }
            
        except Exception as e:
            logger.error(f"Error in rhythmic analysis: {e}")
            return {}
    
    def detect_genre_conventions(
        self,
        harmonic_analysis: Dict[str, Any],
        rhythmic_analysis: Dict[str, Any],
        instrumentation: List[str]
    ) -> Dict[str, Any]:
        """
        Detect genre based on musical conventions
        
        Args:
            harmonic_analysis: Results from analyze_harmonic_progression
            rhythmic_analysis: Results from analyze_rhythmic_complexity
            instrumentation: List of detected instruments/stems
            
        Returns:
            Genre predictions with confidence scores
        """
        try:
            genre_scores = {}
            
            for genre, conventions in self.genre_patterns.items():
                score = 0.0
                reasons = []
                
                # Check harmonic patterns
                if "common_patterns" in harmonic_analysis:
                    for pattern in harmonic_analysis["common_patterns"]:
                        if pattern in conventions.get("common_progressions", []):
                            score += 0.3
                            reasons.append(f"Uses {pattern} progression")
                
                # Check BPM range
                bpm = rhythmic_analysis.get("bpm", 0)
                bpm_range = conventions.get("bpm_range", [0, 300])
                if bpm_range[0] <= bpm <= bpm_range[1]:
                    score += 0.2
                    reasons.append(f"BPM {bpm} matches genre range")
                
                # Check instrumentation
                required_instruments = set(conventions.get("instrumentation", []))
                detected_instruments = set(instrumentation)
                instrument_match = len(required_instruments & detected_instruments) / len(required_instruments) if required_instruments else 0
                score += 0.3 * instrument_match
                if instrument_match > 0.5:
                    reasons.append(f"Instrumentation matches ({int(instrument_match*100)}%)")
                
                # Check rhythmic patterns
                complexity = rhythmic_analysis.get("complexity_score", 0)
                expected_complexity = conventions.get("rhythmic_complexity", 0.5)
                complexity_diff = abs(complexity - expected_complexity)
                if complexity_diff < 0.2:
                    score += 0.2
                    reasons.append("Rhythmic complexity matches")
                
                genre_scores[genre] = {
                    "confidence": min(score, 1.0),
                    "reasons": reasons
                }
            
            # Sort by confidence
            sorted_genres = sorted(
                genre_scores.items(),
                key=lambda x: x[1]["confidence"],
                reverse=True
            )
            
            return {
                "predicted_genres": [
                    {"genre": genre, "confidence": data["confidence"], "reasons": data["reasons"]}
                    for genre, data in sorted_genres[:5]  # Top 5
                ],
                "primary_genre": sorted_genres[0][0] if sorted_genres else "unknown"
            }
            
        except Exception as e:
            logger.error(f"Error in genre detection: {e}")
            return {}
    
    def _parse_key(self, key: str) -> Tuple[str, str]:
        """Parse key string into root and mode"""
        parts = key.split()
        if len(parts) >= 2:
            return parts[0], parts[1].lower()
        return "C", "major"
    
    def _chords_to_roman_numerals(
        self,
        chords: List[Dict[str, Any]],
        key_root: str,
        key_mode: str
    ) -> List[Dict[str, Any]]:
        """
        Convert chord names to Roman numeral notation
        """
        roman_chords = []
        
        # Get key root index
        try:
            key_index = self.NOTE_NAMES.index(key_root)
        except ValueError:
            key_index = 0
        
        for chord in chords:
            chord_name = chord.get("chord", "C")
            
            # Parse chord root
            chord_root = chord_name.split()[0] if ' ' in chord_name else chord_name
            
            try:
                chord_index = self.NOTE_NAMES.index(chord_root)
            except ValueError:
                chord_index = 0
            
            # Calculate scale degree (0-11)
            scale_degree = (chord_index - key_index) % 12
            
            # Convert to Roman numeral based on mode
            if key_mode == "major":
                # Major scale degrees: 0=I, 2=ii, 4=iii, 5=IV, 7=V, 9=vi, 11=vii°
                roman_map = {0: 'I', 2: 'ii', 4: 'iii', 5: 'IV', 7: 'V', 9: 'vi', 11: 'vii°'}
                roman = roman_map.get(scale_degree, 'I')
            else:  # minor
                # Natural minor scale degrees
                roman_map = {0: 'i', 2: 'ii°', 3: 'III', 5: 'iv', 7: 'v', 8: 'VI', 10: 'VII'}
                roman = roman_map.get(scale_degree, 'i')
            
            roman_chords.append({
                "chord": chord_name,
                "roman_numeral": roman,
                "scale_degree": scale_degree,
                "start_time": chord.get("start_time"),
                "end_time": chord.get("end_time"),
                "confidence": chord.get("confidence", 0.7)
            })
        
        return roman_chords
    
    def _analyze_functional_harmony(
        self,
        roman_numerals: List[Dict[str, Any]],
        key_mode: str
    ) -> List[Dict[str, Any]]:
        """
        Analyze functional harmony (tonic, dominant, subdominant)
        """
        functions = []
        
        for chord in roman_numerals:
            roman = chord["roman_numeral"]
            
            # Get function from mapping
            function = self.MAJOR_FUNCTIONS.get(roman, HarmonicFunction.TONIC)
            
            functions.append({
                "roman_numeral": roman,
                "function": function.value,
                "start_time": chord["start_time"],
                "end_time": chord["end_time"]
            })
        
        return functions
    
    def _detect_chord_patterns(self, roman_numerals: List[Dict[str, Any]]) -> List[str]:
        """
        Detect common chord progression patterns
        """
        patterns = []
        
        # Extract just the roman numeral strings
        progression = [c["roman_numeral"] for c in roman_numerals]
        
        # Common patterns to detect
        common_patterns = {
            "I-V-vi-IV": ["I", "V", "vi", "IV"],
            "I-IV-V": ["I", "IV", "V"],
            "ii-V-I": ["ii", "V", "I"],
            "I-vi-IV-V": ["I", "vi", "IV", "V"],
            "vi-IV-I-V": ["vi", "IV", "I", "V"],
            "I-V-IV": ["I", "V", "IV"]
        }
        
        # Check for each pattern
        for pattern_name, pattern_chords in common_patterns.items():
            if self._contains_subsequence(progression, pattern_chords):
                patterns.append(pattern_name)
        
        return patterns
    
    def _contains_subsequence(self, sequence: List[str], subsequence: List[str]) -> bool:
        """Check if subsequence exists in sequence"""
        subseq_len = len(subsequence)
        for i in range(len(sequence) - subseq_len + 1):
            if sequence[i:i+subseq_len] == subsequence:
                return True
        return False
    
    def _calculate_harmonic_rhythm(
        self,
        chords: List[Dict[str, Any]],
        bpm: float
    ) -> Dict[str, Any]:
        """
        Calculate harmonic rhythm (how often chords change)
        """
        if len(chords) < 2:
            return {"avg_duration": 0, "changes_per_bar": 0}
        
        # Calculate average chord duration
        durations = []
        for chord in chords:
            duration = chord.get("end_time", 0) - chord.get("start_time", 0)
            durations.append(duration)
        
        avg_duration = np.mean(durations) if durations else 0
        
        # Calculate changes per bar (assuming 4/4 time)
        seconds_per_bar = (60.0 / bpm) * 4
        changes_per_bar = seconds_per_bar / avg_duration if avg_duration > 0 else 0
        
        return {
            "avg_chord_duration": float(avg_duration),
            "changes_per_bar": float(changes_per_bar),
            "total_chord_changes": len(chords)
        }
    
    def _detect_cadences(
        self,
        roman_numerals: List[Dict[str, Any]],
        chords: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect cadences (musical phrase endings)
        """
        cadences = []
        
        # Look for cadence patterns in last few chords of phrases
        for i in range(len(roman_numerals) - 1):
            current = roman_numerals[i]["roman_numeral"]
            next_chord = roman_numerals[i + 1]["roman_numeral"]
            
            cadence_type = None
            
            # Authentic cadence: V → I
            if current == "V" and next_chord == "I":
                cadence_type = "authentic"
            
            # Plagal cadence: IV → I
            elif current == "IV" and next_chord == "I":
                cadence_type = "plagal"
            
            # Half cadence: any → V
            elif next_chord == "V":
                cadence_type = "half"
            
            # Deceptive cadence: V → vi
            elif current == "V" and next_chord == "vi":
                cadence_type = "deceptive"
            
            if cadence_type:
                cadences.append({
                    "type": cadence_type,
                    "progression": f"{current}-{next_chord}",
                    "time": roman_numerals[i + 1]["start_time"],
                    "strength": self._calculate_cadence_strength(cadence_type)
                })
        
        return cadences
    
    def _calculate_cadence_strength(self, cadence_type: str) -> float:
        """Rate cadence strength (0-1)"""
        strengths = {
            "authentic": 1.0,
            "plagal": 0.8,
            "deceptive": 0.6,
            "half": 0.5
        }
        return strengths.get(cadence_type, 0.5)
    
    def _analyze_voice_leading(
        self,
        chords: List[Dict[str, Any]],
        key_root: str
    ) -> Dict[str, Any]:
        """
        Analyze voice leading quality
        (simplified - full analysis would require note-level data)
        """
        if len(chords) < 2:
            return {"quality": "unknown", "avg_movement": 0}
        
        # Simplified: Assume chord progressions follow good voice leading
        # In reality, would need actual voicings
        
        # Count chord changes
        total_changes = len(chords) - 1
        
        # Estimate movement (simplified)
        # Good voice leading: minimal movement between chords
        movements = []
        
        for i in range(len(chords) - 1):
            # This is simplified - would need actual pitch analysis
            movements.append(2.0)  # Placeholder
        
        avg_movement = np.mean(movements) if movements else 0
        
        # Quality rating
        quality = "good" if avg_movement < 3 else "moderate" if avg_movement < 5 else "poor"
        
        return {
            "quality": quality,
            "avg_movement_semitones": float(avg_movement),
            "total_transitions": total_changes
        }
    
    def _detect_modulations(
        self,
        chords: List[Dict[str, Any]],
        key_root: str,
        key_mode: str
    ) -> List[Dict[str, Any]]:
        """
        Detect key changes (modulations)
        """
        # Simplified implementation
        # Full implementation would use more sophisticated key detection
        modulations = []
        
        # Placeholder - would analyze chord progressions for key changes
        # Look for pivot chords, secondary dominants, etc.
        
        return modulations
    
    def _calculate_progression_complexity(self, roman_numerals: List[Dict[str, Any]]) -> float:
        """
        Calculate how complex the chord progression is (0-1)
        """
        if not roman_numerals:
            return 0.0
        
        # Factors:
        # - Unique chords used (more = complex)
        # - Use of non-diatonic chords
        # - Frequency of changes
        
        unique_chords = len(set(c["roman_numeral"] for c in roman_numerals))
        total_chords = len(roman_numerals)
        
        # Simple complexity metric
        complexity = min(unique_chords / 7.0, 1.0)  # 7 = diatonic chords
        
        return complexity
    
    def _calculate_syncopation(self, beats: List[Dict[str, Any]], bpm: float) -> float:
        """
        Calculate syncopation index (how off-beat the rhythm is)
        """
        if not beats or bpm == 0:
            return 0.0
        
        # Beat duration in seconds
        beat_duration = 60.0 / bpm
        
        # Count beats on/off main beats
        on_beat = 0
        off_beat = 0
        
        for beat in beats:
            beat_time = beat.get("time", 0)
            
            # Calculate position within bar (assuming 4/4)
            beat_position = (beat_time % (beat_duration * 4)) / beat_duration
            
            # Check if on strong beat (1, 3) vs weak beat (2, 4) or off-beat
            if abs(beat_position - round(beat_position)) < 0.1:
                # Close to a beat
                beat_num = int(round(beat_position)) % 4
                if beat_num in [0, 2]:  # Beats 1 and 3 (strong)
                    on_beat += 1
                else:  # Beats 2 and 4 (weak)
                    on_beat += 0.5
            else:
                # Off-beat (syncopated)
                off_beat += 1
        
        total = on_beat + off_beat
        syncopation_index = off_beat / total if total > 0 else 0.0
        
        return min(syncopation_index, 1.0)
    
    def _detect_time_signature(self, beats: List[Dict[str, Any]], bpm: float) -> str:
        """
        Detect time signature from beat pattern
        """
        # Simplified - assume 4/4 for most Western music
        # Full implementation would analyze beat groupings
        return "4/4"
    
    def _detect_polyrhythms(self, beats: List[Dict[str, Any]]) -> bool:
        """
        Detect if multiple rhythmic patterns exist simultaneously
        """
        # Simplified - would require more complex analysis
        # Look for irregular beat patterns
        return False
    
    def _analyze_metric_hierarchy(
        self,
        beats: List[Dict[str, Any]],
        time_signature: str
    ) -> Dict[str, Any]:
        """
        Analyze metric hierarchy (strong vs weak beats)
        """
        # Parse time signature
        numerator = int(time_signature.split('/')[0]) if '/' in time_signature else 4
        
        # Simplified metric hierarchy for 4/4:
        # Beat 1: Strongest (downbeat)
        # Beat 3: Strong
        # Beats 2, 4: Weak (backbeat in popular music)
        
        return {
            "time_signature": time_signature,
            "beats_per_bar": numerator,
            "strong_beats": [1, 3] if numerator == 4 else [1],
            "weak_beats": [2, 4] if numerator == 4 else []
        }
    
    def _calculate_rhythmic_complexity(
        self,
        syncopation: float,
        note_density: float,
        polyrhythms: bool,
        metric_hierarchy: Dict[str, Any]
    ) -> float:
        """
        Calculate overall rhythmic complexity (0-1)
        """
        complexity = 0.0
        
        # Syncopation contributes to complexity
        complexity += syncopation * 0.4
        
        # Note density (normalized)
        normalized_density = min(note_density / 10.0, 1.0)
        complexity += normalized_density * 0.3
        
        # Polyrhythms add complexity
        if polyrhythms:
            complexity += 0.3
        
        return min(complexity, 1.0)
    
    def _load_genre_patterns(self) -> Dict[str, Dict[str, Any]]:
        """
        Load genre convention patterns
        """
        return {
            "pop": {
                "common_progressions": ["I-V-vi-IV", "vi-IV-I-V", "I-IV-V"],
                "bpm_range": [100, 130],
                "instrumentation": ["drums", "bass", "guitar", "vocals", "synth"],
                "rhythmic_complexity": 0.3,
                "typical_structure": "verse-chorus-verse-chorus-bridge-chorus"
            },
            "rock": {
                "common_progressions": ["I-IV-V", "I-V-vi-IV", "I-V-IV"],
                "bpm_range": [110, 150],
                "instrumentation": ["drums", "bass", "guitar", "vocals"],
                "rhythmic_complexity": 0.4,
                "typical_structure": "intro-verse-chorus-verse-chorus-bridge-chorus-outro"
            },
            "jazz": {
                "common_progressions": ["ii-V-I", "I-vi-ii-V"],
                "bpm_range": [80, 180],
                "instrumentation": ["drums", "bass", "piano", "saxophone"],
                "rhythmic_complexity": 0.7,
                "typical_structure": "head-solo-head"
            },
            "edm": {
                "common_progressions": ["I-V-vi-IV", "vi-IV-I-V"],
                "bpm_range": [120, 140],
                "instrumentation": ["drums", "bass", "synth"],
                "rhythmic_complexity": 0.3,
                "typical_structure": "intro-buildup-drop-verse-buildup-drop-outro"
            },
            "hip-hop": {
                "common_progressions": ["i-VI-III-VII", "i-iv-VI-V"],
                "bpm_range": [60, 100],
                "instrumentation": ["drums", "bass", "vocals"],
                "rhythmic_complexity": 0.5,
                "typical_structure": "intro-verse-hook-verse-hook-bridge-hook-outro"
            },
            "country": {
                "common_progressions": ["I-IV-V", "I-V-vi-IV"],
                "bpm_range": [90, 130],
                "instrumentation": ["drums", "bass", "guitar", "vocals"],
                "rhythmic_complexity": 0.3,
                "typical_structure": "verse-chorus-verse-chorus-bridge-chorus"
            }
        }
