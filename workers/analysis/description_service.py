"""
AI Description Generation Service
Generates detailed descriptions for songs and stems using AI models
"""
import os
import logging
from typing import Dict, Any, Optional
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class DescriptionService:
    """
    Service for generating AI-powered descriptions of audio content
    """
    
    def __init__(self):
        """Initialize the description service with Azure AI Foundry client"""
        # Azure AI Foundry endpoint (MLflow tracking URI can be converted to inference endpoint)
        workspace_name = os.getenv("AI_FOUNDRY_WORKSPACE", "aiproject-mo6rlbmgpkrs4")
        region = os.getenv("AI_FOUNDRY_REGION", "eastus2")
        
        # Azure AI Foundry inference endpoint
        self.endpoint = os.getenv(
            "AI_FOUNDRY_ENDPOINT",
            f"https://{workspace_name}.{region}.inference.ml.azure.com"
        )
        
        self.model = os.getenv("AI_FOUNDRY_MODEL", "gpt-4o")
        
        # Use managed identity for authentication
        credential = DefaultAzureCredential()
        
        self.client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=credential
        )
        
        logger.info(f"Using Azure AI Foundry at {self.endpoint} with model: {self.model}")
    
    def generate_song_description(
        self,
        analysis_results: Dict[str, Any],
        audio_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a detailed description of the entire song based on analysis results
        
        Args:
            analysis_results: Dictionary containing BPM, key, sections, chords, etc.
            audio_metadata: Optional metadata (title, artist, genre, etc.)
        
        Returns:
            Detailed description of the song
        """
        try:
            # Build context from analysis results
            bpm = analysis_results.get("bpm", "unknown")
            key = analysis_results.get("key", "unknown")
            sections = analysis_results.get("sections", [])
            chords = analysis_results.get("chords", [])
            
            # Get unique chord progression
            unique_chords = []
            seen = set()
            for chord_info in chords[:20]:  # First 20 chords
                chord = chord_info.get("chord", "N")
                if chord not in seen and chord != "N":
                    unique_chords.append(chord)
                    seen.add(chord)
            
            # Build section structure summary
            section_structure = {}
            for section in sections:
                label = section.get("label", "unknown")
                section_structure[label] = section_structure.get(label, 0) + 1
            
            # Create prompt
            prompt = f"""Analyze this song based on its musical characteristics and generate a detailed, engaging description.

**Musical Analysis:**
- Tempo: {bpm} BPM
- Key: {key}
- Chord Progression: {', '.join(unique_chords[:10]) if unique_chords else 'Not detected'}
- Structure: {', '.join([f"{count} {label}(s)" for label, count in section_structure.items()])}
"""
            
            if audio_metadata:
                title = audio_metadata.get("title", "")
                artist = audio_metadata.get("artist", "")
                genre = audio_metadata.get("genre", "")
                if title or artist or genre:
                    prompt += f"\n**Metadata:**\n"
                    if title:
                        prompt += f"- Title: {title}\n"
                    if artist:
                        prompt += f"- Artist: {artist}\n"
                    if genre:
                        prompt += f"- Genre: {genre}\n"
            
            prompt += """
Write a detailed, professional description (3-4 sentences) that:
1. Describes the overall musical style, mood, and energy
2. Highlights key musical characteristics (tempo, key, structure)
3. Suggests what kind of listener or usage scenario this would suit
4. Uses engaging, descriptive language

Do NOT mention specific artists or copyrighted song names unless provided in metadata. Focus on the musical qualities."""
            
            response = self.client.complete(
                messages=[
                    SystemMessage(content="You are a professional music analyst and writer. Generate engaging, accurate descriptions of songs based on their musical characteristics."),
                    UserMessage(content=prompt)
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=300
            )
            
            description = response.choices[0].message.content.strip()
            logger.info(f"Generated song description: {description[:100]}...")
            return description
            
        except Exception as e:
            logger.error(f"Error generating song description: {str(e)}", exc_info=True)
            return self._generate_fallback_song_description(analysis_results, audio_metadata)
    
    def generate_stem_description(
        self,
        stem_type: str,
        stem_analysis: Dict[str, Any],
        song_analysis: Dict[str, Any]
    ) -> str:
        """
        Generate a detailed description of a specific stem
        
        Args:
            stem_type: Type of stem (vocals, drums, bass, other)
            stem_analysis: Analysis results specific to this stem
            song_analysis: Overall song analysis for context
        
        Returns:
            Detailed description of the stem
        """
        try:
            # Get stem-specific characteristics
            stem_type_lower = stem_type.lower()
            
            # Build stem-specific prompt
            bpm = song_analysis.get("bpm", "unknown")
            key = song_analysis.get("key", "unknown")
            
            # Stem-specific analysis
            rms_level = stem_analysis.get("rms_level", 0)
            peak_level = stem_analysis.get("peak_level", 0)
            spectral_centroid = stem_analysis.get("spectral_centroid", 0)
            zero_crossing_rate = stem_analysis.get("zero_crossing_rate", 0)
            
            prompt = f"""Describe this {stem_type} stem from a musical track based on its characteristics.

**Stem Type:** {stem_type}
**Song Context:**
- Tempo: {bpm} BPM
- Key: {key}

**Audio Characteristics:**
- RMS Level: {rms_level:.4f}
- Peak Level: {peak_level:.4f}
- Spectral Centroid: {spectral_centroid:.2f} Hz
- Zero Crossing Rate: {zero_crossing_rate:.4f}

Write a concise, professional description (2-3 sentences) that:
1. Describes the sonic characteristics and role of this stem
2. Mentions notable qualities (brightness, energy, presence)
3. Explains how it contributes to the overall mix

Use technical but accessible language."""

            response = self.client.complete(
                messages=[
                    SystemMessage(content="You are an audio engineer and music producer. Describe stems with technical accuracy and musical insight."),
                    UserMessage(content=prompt)
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=200
            )
            
            description = response.choices[0].message.content.strip()
            logger.info(f"Generated {stem_type} stem description: {description[:80]}...")
            return description
            
        except Exception as e:
            logger.error(f"Error generating {stem_type} stem description: {str(e)}", exc_info=True)
            return self._generate_fallback_stem_description(stem_type, stem_analysis)
    
    def _generate_fallback_song_description(
        self,
        analysis_results: Dict[str, Any],
        audio_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a basic description without AI when API fails"""
        bpm = analysis_results.get("bpm", "unknown")
        key = analysis_results.get("key", "unknown")
        
        # Determine tempo category
        if isinstance(bpm, (int, float)):
            if bpm < 90:
                tempo_desc = "slow and contemplative"
            elif bpm < 120:
                tempo_desc = "moderate"
            elif bpm < 140:
                tempo_desc = "upbeat and energetic"
            else:
                tempo_desc = "fast-paced and intense"
        else:
            tempo_desc = "varied tempo"
        
        description = f"This track features a {tempo_desc} feel"
        if key != "unknown":
            description += f" in the key of {key}"
        description += f" with a tempo of {bpm} BPM. "
        
        sections = analysis_results.get("sections", [])
        if sections:
            section_types = set(s.get("label", "unknown") for s in sections)
            description += f"The song structure includes {', '.join(section_types)} sections. "
        
        if audio_metadata and audio_metadata.get("genre"):
            description += f"Genre: {audio_metadata['genre']}."
        
        return description
    
    def _generate_fallback_stem_description(
        self,
        stem_type: str,
        stem_analysis: Dict[str, Any]
    ) -> str:
        """Generate a basic stem description without AI when API fails"""
        stem_descriptions = {
            "vocals": "The vocal stem contains the lead and backing vocals, providing the melodic and lyrical content of the track.",
            "drums": "The drum stem features the rhythmic percussion elements including kicks, snares, hi-hats, and cymbals that drive the beat.",
            "bass": "The bass stem delivers the low-frequency foundation with bass guitar or synthesizer, providing harmonic support and rhythmic punch.",
            "other": "This stem contains the remaining instrumental elements such as guitars, keyboards, strings, and other melodic instruments.",
            "guitar": "The guitar stem features acoustic or electric guitar parts, contributing melodic and harmonic elements to the arrangement.",
            "piano": "The piano stem includes keyboard and piano parts, adding harmonic richness and melodic content.",
            "synth": "The synth stem contains synthesizer elements, providing texture, atmosphere, and electronic soundscapes."
        }
        
        base_description = stem_descriptions.get(stem_type.lower(), f"The {stem_type} stem contains isolated audio elements from this track.")
        
        # Add technical details if available
        rms_level = stem_analysis.get("rms_level", 0)
        if rms_level > 0:
            if rms_level > 0.1:
                base_description += " This stem has strong presence in the mix."
            elif rms_level > 0.05:
                base_description += " This stem has moderate level in the mix."
            else:
                base_description += " This stem is more subtle in the mix."
        
        return base_description
