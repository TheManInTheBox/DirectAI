"""
Music Analysis Worker - FastAPI Service
Performs source separation and Music Information Retrieval (MIR) analysis
"""
import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

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
        
        # Step 2: Source separation with Demucs
        logger.info("Starting source separation with Demucs...")
        stems_dir = temp_path / "stems"
        stems_info = await analysis_service.separate_sources(audio_path, stems_dir)
        logger.info(f"Source separation complete. Generated {len(stems_info)} stems")
        
        # Step 3: MIR analysis (BPM, key, sections, chords, beats)
        logger.info("Starting MIR analysis...")
        analysis_results = await analysis_service.analyze_music(audio_path)
        logger.info(f"MIR analysis complete. Detected BPM: {analysis_results.get('bpm')}, Key: {analysis_results.get('key')}")
        
        # Step 4: Generate JAMS annotation
        logger.info("Generating JAMS annotation...")
        jams_data = analysis_service.create_jams_annotation(
            audio_file_id,
            audio_path,
            analysis_results
        )
        jams_path = temp_path / "annotation.jams"
        analysis_service.save_jams(jams_data, jams_path)
        logger.info(f"JAMS annotation saved: {jams_path}")
        
        # Step 5: Upload stems and JAMS to blob storage
        logger.info("Uploading stems and JAMS to blob storage...")
        uploaded_stems = []
        
        # Upload each stem
        for stem_info in stems_info:
            stem_path = stems_dir / stem_info["filename"]
            if stem_path.exists():
                blob_url = await storage_service.upload_stem(
                    audio_file_id,
                    stem_info["stem_type"],
                    stem_path
                )
                uploaded_stems.append({
                    "stem_type": stem_info["stem_type"],
                    "blob_url": blob_url,
                    "file_size_bytes": stem_path.stat().st_size
                })
                logger.info(f"Uploaded stem: {stem_info['stem_type']} -> {blob_url}")
        
        # Upload JAMS annotation
        jams_blob_url = await storage_service.upload_jams(audio_file_id, jams_path)
        logger.info(f"Uploaded JAMS annotation: {jams_blob_url}")
        
        # Step 6: Prepare final response
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        result_payload = {
            "audio_file_id": audio_file_id,
            "status": "completed",
            "processing_time_seconds": processing_time,
            "analysis": {
                "bpm": analysis_results.get("bpm"),
                "key": analysis_results.get("key"),
                "tuning_frequency": analysis_results.get("tuning_frequency"),
                "sections": analysis_results.get("sections", []),
                "chords": analysis_results.get("chords", []),
                "beats": analysis_results.get("beats", [])
            },
            "stems": uploaded_stems,
            "jams_url": jams_blob_url
        }
        
        # Step 7: Send results via callback or log
        if callback_url:
            logger.info(f"Sending results to callback URL: {callback_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(callback_url, json=result_payload)
                response.raise_for_status()
                logger.info(f"Callback successful: {response.status_code}")
        else:
            logger.info(f"Analysis complete for {audio_file_id}. No callback URL provided.")
            logger.info(f"Results: {result_payload}")
        
    except Exception as e:
        logger.error(f"Error processing analysis for {audio_file_id}: {str(e)}", exc_info=True)
        
        # Send error callback if URL provided
        if callback_url:
            error_payload = {
                "audio_file_id": audio_file_id,
                "status": "failed",
                "error": str(e)
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(callback_url, json=error_payload)
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
