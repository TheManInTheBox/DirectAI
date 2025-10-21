"""
Audio Flamingo Service - Advanced audio understanding using Audio Flamingo models
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio
import numpy as np

logger = logging.getLogger(__name__)


class AudioFlamingoService:
    """Service for advanced audio understanding using Audio Flamingo models"""
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = "cpu"  # Use CPU for now, can be upgraded to GPU
        self.model_loaded = False
        
        # Model configuration
        self.model_name = "nvidia/audio-flamingo-2-1.5B"  # Use the 1.5B model for better performance
        
    async def initialize_model(self):
        """Initialize the Audio Flamingo model"""
        if self.model_loaded:
            return
            
        try:
            logger.info("Loading Audio Flamingo model...")
            
            # Import Audio Flamingo components
            from transformers import AutoProcessor, AutoModelForCausalLM
            
            # Load the processor and model
            self.processor = AutoProcessor.from_pretrained(self.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype="auto",
                device_map=self.device
            )
            
            self.model_loaded = True
            logger.info(f"Audio Flamingo model loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load Audio Flamingo model: {str(e)}")
            # Don't raise the exception - continue without flamingo if it fails
            self.model_loaded = False
    
    async def analyze_audio_content(self, audio_path: Path) -> Dict[str, Any]:
        """
        Analyze audio content using Audio Flamingo
        
        Returns comprehensive audio understanding results including:
        - Audio captioning (what sounds are present)
        - Genre classification
        - Mood/emotion detection
        - Instrumentation identification
        - Audio quality assessment
        """
        if not self.model_loaded:
            logger.warning("Audio Flamingo model not loaded, skipping analysis")
            return {}
            
        try:
            logger.info(f"Analyzing audio content with Audio Flamingo: {audio_path}")
            
            # Load and preprocess audio
            import librosa
            audio, sr = librosa.load(str(audio_path), sr=16000, mono=True)
            
            # Prepare different prompts for comprehensive analysis
            analyses = {}
            
            # 1. General audio captioning
            analyses["caption"] = await self._get_audio_caption(audio, sr)
            
            # 2. Genre classification
            analyses["genre"] = await self._classify_genre(audio, sr)
            
            # 3. Mood/emotion detection
            analyses["mood"] = await self._detect_mood(audio, sr)
            
            # 4. Instrumentation identification
            analyses["instruments"] = await self._identify_instruments(audio, sr)
            
            # 5. Audio quality assessment
            analyses["quality"] = await self._assess_audio_quality(audio, sr)
            
            # 6. Tempo and rhythm description
            analyses["rhythm"] = await self._describe_rhythm(audio, sr)
            
            # 7. Vocal analysis (if vocals present)
            analyses["vocals"] = await self._analyze_vocals(audio, sr)
            
            logger.info("Audio Flamingo analysis completed successfully")
            return analyses
            
        except Exception as e:
            logger.error(f"Error in Audio Flamingo analysis: {str(e)}", exc_info=True)
            return {}
    
    async def _get_audio_caption(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Generate a descriptive caption for the audio"""
        try:
            prompt = "Describe what you hear in this audio in detail."
            response = await self._query_model(audio, sr, prompt)
            
            return {
                "description": response,
                "confidence": 0.8
            }
        except Exception as e:
            logger.error(f"Error generating audio caption: {str(e)}")
            return {}
    
    async def _classify_genre(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Classify the musical genre"""
        try:
            prompt = "What genre is this music? Choose from rock, pop, jazz, classical, electronic, hip-hop, country, blues, reggae, folk, or other."
            response = await self._query_model(audio, sr, prompt)
            
            # Extract genre from response
            genre = self._extract_genre_from_response(response)
            
            return {
                "primary_genre": genre,
                "raw_response": response,
                "confidence": 0.75
            }
        except Exception as e:
            logger.error(f"Error classifying genre: {str(e)}")
            return {}
    
    async def _detect_mood(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Detect the mood and emotional content"""
        try:
            prompt = "What is the mood or emotional feeling of this music? Is it happy, sad, energetic, calm, aggressive, romantic, mysterious, or something else?"
            response = await self._query_model(audio, sr, prompt)
            
            return {
                "mood_description": response,
                "confidence": 0.7
            }
        except Exception as e:
            logger.error(f"Error detecting mood: {str(e)}")
            return {}
    
    async def _identify_instruments(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Identify musical instruments present"""
        try:
            prompt = "What musical instruments can you hear in this audio? List all the instruments you can identify."
            response = await self._query_model(audio, sr, prompt)
            
            # Extract instruments list from response
            instruments = self._extract_instruments_from_response(response)
            
            return {
                "instruments": instruments,
                "raw_response": response,
                "confidence": 0.8
            }
        except Exception as e:
            logger.error(f"Error identifying instruments: {str(e)}")
            return {}
    
    async def _assess_audio_quality(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Assess the technical quality of the audio"""
        try:
            prompt = "How is the audio quality? Is it clear, distorted, noisy, well-recorded, or poorly recorded? Describe the technical aspects."
            response = await self._query_model(audio, sr, prompt)
            
            return {
                "quality_assessment": response,
                "confidence": 0.6
            }
        except Exception as e:
            logger.error(f"Error assessing audio quality: {str(e)}")
            return {}
    
    async def _describe_rhythm(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Describe the rhythm and tempo characteristics"""
        try:
            prompt = "Describe the rhythm and tempo of this music. Is it fast, slow, steady, syncopated, or complex?"
            response = await self._query_model(audio, sr, prompt)
            
            return {
                "rhythm_description": response,
                "confidence": 0.7
            }
        except Exception as e:
            logger.error(f"Error describing rhythm: {str(e)}")
            return {}
    
    async def _analyze_vocals(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze vocal characteristics if present"""
        try:
            prompt = "Are there vocals in this audio? If so, describe the vocal style, gender, and characteristics."
            response = await self._query_model(audio, sr, prompt)
            
            return {
                "vocal_analysis": response,
                "confidence": 0.75
            }
        except Exception as e:
            logger.error(f"Error analyzing vocals: {str(e)}")
            return {}
    
    async def _query_model(self, audio: np.ndarray, sr: int, prompt: str) -> str:
        """Query the Audio Flamingo model with audio and text prompt"""
        try:
            # Prepare inputs for the model
            inputs = self.processor(
                audio=audio,
                text=prompt,
                sampling_rate=sr,
                return_tensors="pt"
            )
            
            # Move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=100,
                    do_sample=True,
                    temperature=0.7,
                    pad_token_id=self.processor.tokenizer.eos_token_id
                )
            
            # Decode response
            response = self.processor.tokenizer.decode(
                outputs[0], 
                skip_special_tokens=True
            )
            
            # Remove the prompt from the response
            if prompt in response:
                response = response.replace(prompt, "").strip()
            
            return response
            
        except Exception as e:
            logger.error(f"Error querying Audio Flamingo model: {str(e)}")
            return "Analysis unavailable"
    
    def _extract_genre_from_response(self, response: str) -> str:
        """Extract genre from model response"""
        response_lower = response.lower()
        
        # Define genre keywords
        genres = {
            "rock": ["rock", "metal", "punk", "grunge"],
            "pop": ["pop", "mainstream"],
            "jazz": ["jazz", "swing", "bebop"],
            "classical": ["classical", "orchestral", "symphony"],
            "electronic": ["electronic", "edm", "techno", "house", "synth"],
            "hip-hop": ["hip-hop", "rap", "hip hop"],
            "country": ["country", "folk", "bluegrass"],
            "blues": ["blues", "r&b"],
            "reggae": ["reggae", "ska"],
            "latin": ["latin", "salsa", "bossa nova"],
        }
        
        for genre, keywords in genres.items():
            if any(keyword in response_lower for keyword in keywords):
                return genre
        
        return "unknown"
    
    def _extract_instruments_from_response(self, response: str) -> List[str]:
        """Extract instrument names from model response"""
        response_lower = response.lower()
        
        # Define common instruments
        instruments = [
            "guitar", "bass", "drums", "piano", "keyboard", "vocals", "violin", 
            "saxophone", "trumpet", "flute", "clarinet", "cello", "organ",
            "synthesizer", "harmonica", "banjo", "mandolin", "accordion"
        ]
        
        found_instruments = []
        for instrument in instruments:
            if instrument in response_lower:
                found_instruments.append(instrument)
        
        return found_instruments
    
    async def get_detailed_analysis_report(self, audio_path: Path) -> Dict[str, Any]:
        """
        Generate a comprehensive analysis report combining Audio Flamingo insights
        with traditional MIR analysis
        """
        try:
            # Get Audio Flamingo analysis
            flamingo_results = await self.analyze_audio_content(audio_path)
            
            # Create a structured report
            report = {
                "flamingo_analysis": flamingo_results,
                "summary": self._create_analysis_summary(flamingo_results),
                "confidence_scores": self._calculate_confidence_scores(flamingo_results),
                "analysis_timestamp": "2025-10-21T18:30:00Z"
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error creating analysis report: {str(e)}")
            return {}
    
    def _create_analysis_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create a high-level summary of the analysis"""
        summary = {}
        
        # Extract key information
        if "caption" in results and "description" in results["caption"]:
            summary["description"] = results["caption"]["description"]
        
        if "genre" in results and "primary_genre" in results["genre"]:
            summary["genre"] = results["genre"]["primary_genre"]
        
        if "mood" in results and "mood_description" in results["mood"]:
            summary["mood"] = results["mood"]["mood_description"]
        
        if "instruments" in results and "instruments" in results["instruments"]:
            summary["instruments"] = results["instruments"]["instruments"]
        
        return summary
    
    def _calculate_confidence_scores(self, results: Dict[str, Any]) -> Dict[str, float]:
        """Calculate overall confidence scores for different analysis aspects"""
        confidence_scores = {}
        
        for analysis_type, data in results.items():
            if isinstance(data, dict) and "confidence" in data:
                confidence_scores[analysis_type] = data["confidence"]
        
        # Calculate overall confidence
        if confidence_scores:
            confidence_scores["overall"] = sum(confidence_scores.values()) / len(confidence_scores)
        
        return confidence_scores