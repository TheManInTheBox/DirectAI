"""
Music Generation Worker - FastAPI Service
Generates new audio stems using AI models (Stable Audio Open, MusicGen)
"""
import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx

from generation_service import GenerationService
from storage_service import StorageService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Music Generation Worker",
    description="AI-powered audio stem generation service",
    version="1.0.0"
)

# Initialize services
storage_service = StorageService()
generation_service = GenerationService(storage_service=storage_service)

# Request/Response models
class GenerationParameters(BaseModel):
    """Generation parameters for conditioning"""
    target_bpm: Optional[float] = Field(None, description="Target tempo in BPM")
    duration_seconds: Optional[float] = Field(10.0, description="Generated audio duration")
    style: Optional[str] = Field(None, description="Musical style/genre")
    chord_progression: Optional[List[str]] = Field(None, description="Chord sequence")
    prompt: Optional[str] = Field(None, description="Text prompt for generation")
    temperature: Optional[float] = Field(1.0, description="Generation randomness (0.0-2.0)")
    random_seed: Optional[int] = Field(None, description="Random seed for reproducibility")


class GenerateRequest(BaseModel):
    """Request model for generation endpoint"""
    generation_request_id: str = Field(..., description="GUID of the generation request")
    audio_file_id: str = Field(..., description="GUID of the source audio file")
    target_stems: List[str] = Field(..., description="Stem types to generate (vocals, drums, bass, guitar, etc.)")
    parameters: GenerationParameters = Field(..., description="Generation parameters")
    callback_url: Optional[str] = Field(None, description="Optional callback URL for results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "generation_request_id": "gen-123e4567-e89b-12d3-a456-426614174000",
                "audio_file_id": "aud-123e4567-e89b-12d3-a456-426614174000",
                "target_stems": ["guitar", "bass", "drums"],
                "parameters": {
                    "target_bpm": 120.0,
                    "duration_seconds": 30.0,
                    "style": "rock",
                    "chord_progression": ["C", "G", "Am", "F"],
                    "prompt": "energetic rock guitar with distortion",
                    "temperature": 1.0
                },
                "callback_url": "http://api:8080/api/generation/callback"
            }
        }


class GenerationResponse(BaseModel):
    """Response model for generation results"""
    generation_request_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    services: Dict[str, str]
    gpu_available: bool


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    import torch
    
    gpu_available = torch.cuda.is_available()
    
    services_status = {
        "musicgen": "available" if generation_service.has_musicgen else "not_loaded",
        "storage": "connected" if storage_service.is_connected() else "disconnected",
        "device": "gpu" if gpu_available else "cpu"
    }
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        services=services_status,
        gpu_available=gpu_available
    )


@app.post("/generate", response_model=GenerationResponse)
async def generate_stems(
    request: GenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    Main generation endpoint - creates new audio stems using AI models
    
    Process:
    1. Validate generation request
    2. Load conditioning parameters (BPM, chords, style, prompt)
    3. Generate stems using appropriate models:
       - Stable Audio Open: General audio generation
       - MusicGen: Music-specific generation
    4. Upload generated stems to blob storage
    5. Return results (or call callback URL)
    """
    logger.info(f"Received generation request: {request.generation_request_id}")
    
    try:
        # Validate target stems
        valid_stems = {"vocals", "drums", "bass", "guitar", "piano", "synth", "other"}
        invalid_stems = set(request.target_stems) - valid_stems
        if invalid_stems:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid stem types: {invalid_stems}. Valid: {valid_stems}"
            )
        
        # Start background generation task
        background_tasks.add_task(
            process_generation,
            request.generation_request_id,
            request.audio_file_id,
            request.target_stems,
            request.parameters.model_dump(),
            request.callback_url
        )
        
        return GenerationResponse(
            generation_request_id=request.generation_request_id,
            status="processing",
            message="Generation started. Stems will be available shortly."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start generation: {str(e)}")


async def process_generation(
    generation_request_id: str,
    audio_file_id: str,
    target_stems: List[str],
    parameters: Dict[str, Any],
    callback_url: Optional[str]
):
    """
    Background task to process stem generation
    """
    temp_dir = None
    start_time = datetime.utcnow()
    
    try:
        logger.info(f"Starting generation processing for {generation_request_id}")
        
        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"generation_{generation_request_id}_")
        temp_path = Path(temp_dir)
        
        generated_stems = []
        
        # Generate each requested stem
        for stem_type in target_stems:
            logger.info(f"Generating stem: {stem_type}")
            
            try:
                # Generate audio using AI models
                audio_path = await generation_service.generate_stem(
                    stem_type=stem_type,
                    parameters=parameters,
                    output_dir=temp_path
                )
                
                if not audio_path or not audio_path.exists():
                    logger.warning(f"Failed to generate stem: {stem_type}")
                    continue
                
                logger.info(f"Generated {stem_type}: {audio_path.stat().st_size} bytes")
                
                # Upload to blob storage
                blob_url = await storage_service.upload_generated_stem(
                    generation_request_id=generation_request_id,
                    audio_file_id=audio_file_id,
                    stem_type=stem_type,
                    local_path=audio_path
                )
                
                generated_stems.append({
                    "stem_type": stem_type,
                    "blob_url": blob_url,
                    "file_size_bytes": audio_path.stat().st_size,
                    "format": "wav",
                    "sample_rate": 44100,
                    "channels": 2
                })
                
                logger.info(f"Uploaded {stem_type} stem: {blob_url}")
                
            except Exception as stem_error:
                logger.error(f"Error generating stem {stem_type}: {str(stem_error)}")
                # Continue with other stems
        
        if not generated_stems:
            raise RuntimeError("No stems were successfully generated")
        
        # Prepare final response
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        result_payload = {
            "generation_request_id": generation_request_id,
            "audio_file_id": audio_file_id,
            "status": "completed",
            "processing_time_seconds": processing_time,
            "generated_stems": generated_stems,
            "parameters": parameters
        }
        
        # Send results via callback or log
        if callback_url:
            logger.info(f"Sending results to callback URL: {callback_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(callback_url, json=result_payload)
                response.raise_for_status()
                logger.info(f"Callback successful: {response.status_code}")
        else:
            logger.info(f"Generation complete for {generation_request_id}. No callback URL provided.")
            logger.info(f"Results: {result_payload}")
        
    except Exception as e:
        logger.error(f"Error processing generation for {generation_request_id}: {str(e)}", exc_info=True)
        
        # Send error callback if URL provided
        if callback_url:
            error_payload = {
                "generation_request_id": generation_request_id,
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
        "service": "Music Generation Worker",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "generate": "/generate (POST)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
