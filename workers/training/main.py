import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from training_service import MusicGenTrainingService
from storage_service import StorageService
from database_service import DatabaseService
from queue_listener import TrainingQueueListener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
training_service: MusicGenTrainingService = None
storage_service: StorageService = None
db_service: DatabaseService = None
queue_listener: Optional[TrainingQueueListener] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global training_service, storage_service, db_service, queue_listener
    
    logger.info("Initializing training worker services...")
    
    # Initialize storage service
    storage_service = StorageService(
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        container_name=os.getenv("BLOB_CONTAINER_NAME", "audio-files")
    )
    await storage_service.initialize()
    
    # Initialize database service
    db_service = DatabaseService(
        connection_string=os.getenv("DATABASE_URL")
    )
    await db_service.initialize()
    
    # Initialize training service
    training_service = MusicGenTrainingService(
        storage_service=storage_service,
        db_service=db_service,
        use_gpu=os.getenv("USE_GPU", "true").lower() == "true"
    )
    await training_service.initialize()
    
    # Start queue listener if enabled
    if os.getenv("ENABLE_QUEUE_LISTENER", "true").lower() == "true":
        queue_listener = TrainingQueueListener(training_service=training_service)
        asyncio.create_task(queue_listener.start())
        logger.info("Queue listener started")
    
    logger.info("Training worker initialized successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down training worker...")
    if queue_listener:
        await queue_listener.stop()
    await training_service.cleanup()
    await db_service.close()

app = FastAPI(
    title="MusicGen Training Worker",
    description="LoRA fine-tuning service for MusicGen models",
    version="1.0.0",
    lifespan=lifespan
)

# Request/Response models
class TrainRequest(BaseModel):
    dataset_id: str
    model_name: str
    epochs: int = 100
    learning_rate: float = 1e-4
    lora_rank: int = 8
    lora_alpha: int = 16
    batch_size: int = 1

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "training": "ready" if training_service and training_service.is_initialized else "not_ready",
            "storage": "ready" if storage_service and storage_service.is_initialized else "not_ready",
            "database": "ready" if db_service and db_service.is_initialized else "not_ready"
        },
        "device": training_service.device if training_service else "unknown"
    }

@app.post("/train")
async def train_model(request: TrainRequest):
    """Start a training job"""
    if not training_service or not training_service.is_initialized:
        raise HTTPException(status_code=503, detail="Training service not initialized")
    
    logger.info(f"Received training request for dataset {request.dataset_id}")
    
    try:
        result = await training_service.train_model(
            dataset_id=request.dataset_id,
            model_name=request.model_name,
            epochs=request.epochs,
            learning_rate=request.learning_rate,
            lora_rank=request.lora_rank,
            lora_alpha=request.lora_alpha,
            batch_size=request.batch_size
        )
        
        return {
            "status": "success",
            "model_id": result["model_id"],
            "model_path": result["model_path"],
            "training_time_seconds": result["training_time"],
            "final_loss": result.get("final_loss")
        }
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{dataset_id}")
async def get_training_status(dataset_id: str):
    """Get training status for a dataset"""
    if not db_service:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    
    try:
        status = await db_service.get_training_status(dataset_id)
        if not status:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get training status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        log_level="info"
    )
