"""
Music Analysis Worker - FastAPI Service
Performs source separation and Music Information Retrieval (MIR) analysis
"""
import os
import tempfile
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx

from analysis_service import AnalysisService
from storage_service import StorageService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Music Analysis Worker",
    description="Audio source separation and MIR analysis service",
    version="1.0.0"
)

# Initialize services
storage_service = StorageService()
analysis_service = AnalysisService()

# Request/Response models
class AnalyzeRequest(BaseModel):
    """Request model for analysis endpoint"""
    audio_file_id: str = Field(..., description="GUID of the audio file")
    blob_uri: str = Field(..., description="Blob storage URI of the audio file")
    callback_url: Optional[str] = Field(None, description="Optional callback URL for results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "audio_file_id": "123e4567-e89b-12d3-a456-426614174000",
                "blob_uri": "https://storage.blob.core.windows.net/audio-files/song.mp3",
                "callback_url": "http://api:5000/api/audio/analysis-callback"
            }
        }

class AnalysisResponse(BaseModel):
    """Response model for analysis results"""
    audio_file_id: str
    status: str
    message: str
    duration_seconds: Optional[float] = None
    
class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    services: Dict[str, str]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services_status = {
        "demucs": "available",
        "essentia": "available",
        "madmom": "available",
        "storage": "connected" if storage_service.is_connected() else "disconnected"
    }
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        services=services_status
    )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_audio(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks
):
    """
    Main analysis endpoint - performs source separation and MIR analysis
    
    Process:
    1. Download audio file from blob storage
    2. Separate sources with Demucs (vocals, drums, bass, other)
    3. Extract MIR features (BPM, key, sections, chords, beats)
    4. Generate JAMS annotation
    5. Upload stems and JAMS to blob storage
    6. Return analysis results (or call callback URL)
    """
    logger.info(f"Received analysis request for audio_file_id: {request.audio_file_id}")
    
    try:
        # Validate blob URI
        if not request.blob_uri.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Invalid blob URI format")
        
        # Start background analysis task
        background_tasks.add_task(
            process_analysis,
            request.audio_file_id,
            request.blob_uri,
            request.callback_url
        )
        
        return AnalysisResponse(
            audio_file_id=request.audio_file_id,
            status="processing",
            message="Analysis started. Results will be available shortly."
        )
        
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


async def process_analysis(
    audio_file_id: str,
    blob_uri: str,
    callback_url: Optional[str]
):
    """
    Background task to process audio analysis
    """
    temp_dir = None
    start_time = datetime.utcnow()
    
    try:
        logger.info(f"Starting analysis processing for {audio_file_id}")
        
        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"analysis_{audio_file_id}_")
        temp_path = Path(temp_dir)
        
        # Step 1: Download audio file from blob storage
        logger.info(f"Downloading audio file from {blob_uri}")
        audio_path = temp_path / "original.mp3"
        await storage_service.download_blob(blob_uri, audio_path)
        
        if not audio_path.exists():
            raise RuntimeError("Failed to download audio file from blob storage")
        
        logger.info(f"Downloaded audio file: {audio_path.stat().st_size} bytes")
        
        # Step 2: Extract MP3 metadata (ID3 tags)
        logger.info("Extracting MP3 metadata...")
        mp3_metadata = await analysis_service.extract_mp3_metadata(audio_path)
        logger.info(f"MP3 metadata extraction complete. Found {len(mp3_metadata)} fields")
        
        # Step 3: Source separation with Demucs (4-stem: vocals, drums, bass, other)
        logger.info("Starting source separation with Demucs...")
        stems_dir = temp_path / "stems"
        stems_info = await analysis_service.separate_sources(audio_path, stems_dir)
        logger.info(f"Source separation complete. Generated {len(stems_info)} stems")
        
        # Step 4: MIR analysis (BPM, key, sections, chords, beats)
        logger.info("Starting MIR analysis...")
        analysis_results = await analysis_service.analyze_music(audio_path)
        logger.info(f"MIR analysis complete. Detected BPM: {analysis_results.get('bpm')}, Key: {analysis_results.get('key')}")
        
        # Step 5: Generate JAMS annotation
        logger.info("Generating JAMS annotation...")
        jams_data = analysis_service.create_jams_annotation(
            audio_file_id,
            audio_path,
            analysis_results
        )
        jams_path = temp_path / "annotation.jams"
        analysis_service.save_jams(jams_data, jams_path)
        logger.info(f"JAMS annotation saved: {jams_path}")
        
        # Step 6: Upload stems and JAMS to blob storage
        logger.info("Uploading stems and JAMS to blob storage...")
        uploaded_stems = []
        
        # Map Demucs stem names to StemType enum values
        stem_type_mapping = {
            'vocals': 'Vocals',
            'drums': 'Drums', 
            'bass': 'Bass',
            'other': 'Other',    # Other instruments (guitar, piano, etc.)
            'no_vocals': 'Other',  # Fallback for 2-stem mode
            'accompaniment': 'Other'  # Fallback for 2-stem mode
        }
        
        # Upload each stem and create database records
        for stem_info in stems_info:
            stem_path = Path(stem_info["path"])
            if stem_path.exists():
                # Map stem type to enum value
                demucs_stem_type = stem_info["stem_type"].lower()
                stem_type = stem_type_mapping.get(demucs_stem_type, 'Other')
                
                # Upload stem to blob storage
                blob_url = await storage_service.upload_stem(
                    audio_file_id,
                    stem_info["stem_type"],
                    stem_path
                )
                
                # Skip full MIR analysis for stems - inherit BPM/key/chords from main audio
                # (Stems share the same tempo, key, and chord progression as the source)
                logger.info(f"Using main audio BPM/key/chords for {stem_info['stem_type']} stem (skipping MIR analysis)...")
                stem_analysis = {
                    "bpm": analysis_results.get("bpm"),
                    "key": analysis_results.get("key"),
                    "tuning_frequency": analysis_results.get("tuning_frequency"),
                    "beats": analysis_results.get("beats", []),  # Use main audio beats
                    "chords": analysis_results.get("chords", []),  # Use main audio chords
                    "sections": analysis_results.get("sections", [])  # Use main audio sections
                }
                
                # Extract notation for guitar, bass, and drums
                notation_data = {}
                if stem_type in ['Drums', 'Bass', 'Other']:  # Other includes guitar
                    logger.info(f"Extracting notation for {stem_type} stem...")
                    notation_data = await analysis_service.extract_notation(
                        stem_path, 
                        stem_type.lower(), 
                        sr=22050
                    )
                
                # Calculate audio quality metrics for this stem
                import librosa
                y_stem, sr_stem = librosa.load(str(stem_path), sr=44100, mono=True)
                rms_level = float(np.sqrt(np.mean(y_stem**2)))
                peak_level = float(np.max(np.abs(y_stem)))
                spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y_stem, sr=sr_stem)))
                zero_crossing_rate = float(np.mean(librosa.feature.zero_crossing_rate(y_stem)))
                
                # Prepare stem data for API (include MP3 metadata context)
                stem_data = {
                    "audioFileId": audio_file_id,
                    "type": stem_type,  # Use mapped enum value
                    "blobUri": blob_url,
                    "durationSeconds": len(y_stem) / sr_stem,  # Duration in seconds as float
                    "fileSizeBytes": stem_path.stat().st_size,
                    "sourceSeparationModel": "htdemucs",
                    
                    # Musical metadata from analysis
                    "bpm": stem_analysis.get("bpm"),
                    "key": stem_analysis.get("key"),
                    "timeSignature": "4/4",  # Default for now
                    "tuningFrequency": stem_analysis.get("tuning_frequency"),
                    
                    # Audio quality metrics
                    "rmsLevel": rms_level,
                    "peakLevel": peak_level,
                    "spectralCentroid": spectral_centroid,
                    "zeroCrossingRate": zero_crossing_rate,
                    
                    # Musical structure as JSON strings
                    "chordProgression": json.dumps(stem_analysis.get("chords", [])),
                    "beats": json.dumps(stem_analysis.get("beats", [])),
                    "sections": json.dumps(stem_analysis.get("sections", [])),
                    
                    # Musical notation data (NEW)
                    "notationData": json.dumps(notation_data) if notation_data else None,
                    
                    # Analysis status
                    "analysisStatus": "Completed",
                    "analyzedAt": datetime.utcnow().isoformat() + 'Z'  # Add Z for UTC timezone
                }
                
                # Create stem record in database via API
                try:
                    api_base_url = os.getenv("API_BASE_URL", "http://music-api:8080")
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            f"{api_base_url}/api/stems",
                            json=stem_data
                        )
                        if response.status_code == 201:
                            logger.info(f"Created stem record for {stem_info['stem_type']} -> {stem_type}")
                        else:
                            logger.warning(f"Failed to create stem record: {response.status_code} - {response.text}")
                except Exception as api_error:
                    logger.error(f"Error creating stem record: {api_error}")
                
                uploaded_stems.append({
                    "stem_type": stem_info["stem_type"],
                    "mapped_type": stem_type,
                    "blob_url": blob_url,
                    "file_size_bytes": stem_path.stat().st_size,
                    "metadata": stem_analysis
                })
                logger.info(f"Uploaded and analyzed stem: {stem_info['stem_type']} -> {stem_type} -> {blob_url}")
        
        # Step 7: Upload album artwork if present and update AudioFile metadata
        album_artwork_uri = None
        logger.info(f"Checking for album artwork in metadata: {', '.join(mp3_metadata.keys())}")
        if 'album_artwork_data' in mp3_metadata:
            try:
                logger.info("Uploading album artwork...")
                artwork_data = mp3_metadata.pop('album_artwork_data')
                artwork_mime = mp3_metadata.pop('album_artwork_mime', 'image/jpeg')
                album_artwork_uri = await storage_service.upload_album_artwork(
                    audio_file_id,
                    artwork_data,
                    artwork_mime
                )
                logger.info(f"Uploaded album artwork: {album_artwork_uri}")
            except Exception as artwork_error:
                logger.error(f"Error uploading album artwork: {artwork_error}")
        else:
            logger.info("No album artwork data found in metadata")
        
        # Step 8: Update AudioFile record with MP3 metadata AND analysis results
        logger.info("Updating AudioFile with MP3 metadata and analysis results...")
        metadata_update = {
            "title": mp3_metadata.get("title"),
            "artist": mp3_metadata.get("artist"),
            "album": mp3_metadata.get("album"),
            "albumArtist": mp3_metadata.get("album_artist"),
            "year": mp3_metadata.get("year"),
            "genre": mp3_metadata.get("genre"),
            "trackNumber": mp3_metadata.get("track_number"),
            "discNumber": mp3_metadata.get("disc_number"),
            "composer": mp3_metadata.get("composer"),
            "conductor": mp3_metadata.get("conductor"),
            "comment": mp3_metadata.get("comment"),
            "albumArtworkUri": album_artwork_uri,
            "bitrate": mp3_metadata.get("bitrate"),
            "sampleRate": mp3_metadata.get("sample_rate"),
            "channels": mp3_metadata.get("channels"),
            "audioMode": str(mp3_metadata.get("mode")) if mp3_metadata.get("mode") else None,
            "mp3Version": str(mp3_metadata.get("version")) if mp3_metadata.get("version") else None,
            "bpmTag": mp3_metadata.get("bpm_tag"),
            "keyTag": mp3_metadata.get("key_tag"),
            # Add analysis results
            "bpm": analysis_results.get("bpm"),
            "key": analysis_results.get("key"),
            "timeSignature": "4/4"  # Default for now, could be detected in future
        }
        
        try:
            api_base_url = os.getenv("API_BASE_URL", "http://music-api:8080")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{api_base_url}/api/audio/{audio_file_id}/metadata",
                    json=metadata_update
                )
                if response.status_code == 200:
                    logger.info("Successfully updated AudioFile metadata")
                else:
                    logger.warning(f"Failed to update metadata: {response.status_code} - {response.text}")
        except Exception as metadata_error:
            logger.error(f"Error updating AudioFile metadata: {metadata_error}")
        
        # Upload JAMS annotation
        jams_blob_url = await storage_service.upload_jams(audio_file_id, jams_path)
        logger.info(f"Uploaded JAMS annotation: {jams_blob_url}")
        
        # Step 9: Prepare final response
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Step 10: Send success callback
        if callback_url:
            logger.info(f"Sending success callback to: {callback_url}")
            success_payload = {
                "success": True,
                "error_message": None
            }
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(callback_url, json=success_payload)
                    response.raise_for_status()
                    logger.info(f"Success callback sent: {response.status_code}")
            except Exception as callback_error:
                logger.error(f"Failed to send success callback: {callback_error}")
        else:
            logger.info(f"Analysis complete for {audio_file_id}. No callback URL provided.")
        
        logger.info(f"Analysis completed successfully in {processing_time:.2f}s")
        
    except Exception as e:
        logger.error(f"Error processing analysis for {audio_file_id}: {str(e)}", exc_info=True)
        
        # Send error callback if URL provided
        if callback_url:
            error_payload = {
                "success": False,
                "error_message": str(e)
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(callback_url, json=error_payload)
                    logger.info("Error callback sent successfully")
            except Exception as callback_error:
                logger.error(f"Failed to send error callback: {callback_error}")
    
    finally:
        # Cleanup temporary directory
        if temp_dir and Path(temp_dir).exists():
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp directory: {cleanup_error}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Music Analysis Worker",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze (POST)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
