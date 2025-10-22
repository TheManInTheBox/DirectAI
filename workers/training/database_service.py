import logging
import asyncpg
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseService:
    """Service for database operations"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize database connection pool"""
        logger.info("Initializing database connection pool...")
        
        self.pool = await asyncpg.create_pool(
            dsn=self.connection_string,
            min_size=2,
            max_size=10
        )
        
        logger.info("Database connection pool initialized")
        self.is_initialized = True
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def get_training_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Fetch training dataset with stems"""
        async with self.pool.acquire() as conn:
            # Get dataset
            dataset_row = await conn.fetchrow(
                '''
                SELECT 
                    "Id", "Name", "Description", "Status", 
                    "TotalDurationSeconds", "StemCount", "Metadata"
                FROM "TrainingDatasets"
                WHERE "Id" = $1
                ''',
                dataset_id
            )
            
            if not dataset_row:
                return None
            
            # Get stems
            stem_rows = await conn.fetch(
                '''
                SELECT 
                    tds."Id", tds."StemId", tds."Weight", tds."Order",
                    s."BlobPath", s."Type", s."DurationSeconds"
                FROM "TrainingDatasetStems" tds
                JOIN "Stems" s ON tds."StemId" = s."Id"
                WHERE tds."TrainingDatasetId" = $1
                ORDER BY tds."Order"
                ''',
                dataset_id
            )
            
            return {
                "id": str(dataset_row["Id"]),
                "name": dataset_row["Name"],
                "description": dataset_row["Description"],
                "status": dataset_row["Status"],
                "total_duration_seconds": dataset_row["TotalDurationSeconds"],
                "stem_count": dataset_row["StemCount"],
                "metadata": json.loads(dataset_row["Metadata"]) if dataset_row["Metadata"] else {},
                "stems": [
                    {
                        "id": str(row["StemId"]),
                        "weight": row["Weight"],
                        "order": row["Order"],
                        "blob_path": row["BlobPath"],
                        "type": row["Type"],
                        "duration_seconds": row["DurationSeconds"]
                    }
                    for row in stem_rows
                ]
            }
    
    async def create_trained_model(
        self,
        dataset_id: str,
        name: str,
        base_model: str
    ) -> str:
        """Create a new trained model record"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                '''
                INSERT INTO "TrainedModels" (
                    "Id", "TrainingDatasetId", "Name", "BaseModel",
                    "ModelPath", "ModelSizeBytes", 
                    "TrainingConfig", "TrainingMetrics",
                    "Status", "CreatedAt", "UsageCount"
                )
                VALUES ($1, $2, $3, $4, '', 0, '{}', '{}', 'Pending', $5, 0)
                RETURNING "Id"
                ''',
                dataset_id,  # Use dataset_id as model Id initially
                dataset_id,
                name,
                base_model,
                datetime.utcnow()
            )
            
            model_id = str(row["Id"])
            logger.info(f"Created trained model record {model_id}")
            return model_id
    
    async def update_training_dataset_status(
        self,
        dataset_id: str,
        status: str
    ) -> None:
        """Update training dataset status"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                UPDATE "TrainingDatasets"
                SET "Status" = $1, "UpdatedAt" = $2
                WHERE "Id" = $3
                ''',
                status,
                datetime.utcnow(),
                dataset_id
            )
            
            logger.info(f"Updated dataset {dataset_id} status to {status}")
    
    async def update_trained_model_status(
        self,
        model_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update trained model status"""
        async with self.pool.acquire() as conn:
            if status == "Training":
                await conn.execute(
                    '''
                    UPDATE "TrainedModels"
                    SET "Status" = $1, "TrainingStartedAt" = $2
                    WHERE "Id" = $3
                    ''',
                    status,
                    datetime.utcnow(),
                    model_id
                )
            elif status == "Ready":
                await conn.execute(
                    '''
                    UPDATE "TrainedModels"
                    SET "Status" = $1, "TrainingCompletedAt" = $2
                    WHERE "Id" = $3
                    ''',
                    status,
                    datetime.utcnow(),
                    model_id
                )
            elif status == "Failed":
                await conn.execute(
                    '''
                    UPDATE "TrainedModels"
                    SET "Status" = $1, "ErrorMessage" = $2
                    WHERE "Id" = $3
                    ''',
                    status,
                    error_message,
                    model_id
                )
            else:
                await conn.execute(
                    '''
                    UPDATE "TrainedModels"
                    SET "Status" = $1
                    WHERE "Id" = $2
                    ''',
                    status,
                    model_id
                )
            
            logger.info(f"Updated model {model_id} status to {status}")
    
    async def update_trained_model(
        self,
        model_id: str,
        model_path: str,
        model_size_bytes: int,
        training_config: Dict[str, Any],
        training_metrics: Dict[str, Any],
        status: str
    ) -> None:
        """Update trained model with completion data"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                UPDATE "TrainedModels"
                SET 
                    "ModelPath" = $1,
                    "ModelSizeBytes" = $2,
                    "TrainingConfig" = $3,
                    "TrainingMetrics" = $4,
                    "Status" = $5,
                    "TrainingCompletedAt" = $6
                WHERE "Id" = $7
                ''',
                model_path,
                model_size_bytes,
                json.dumps(training_config),
                json.dumps(training_metrics),
                status,
                datetime.utcnow(),
                model_id
            )
            
            logger.info(f"Updated model {model_id} with training results")
    
    async def update_training_metrics(
        self,
        model_id: str,
        metrics: Dict[str, Any]
    ) -> None:
        """Update training metrics during training"""
        async with self.pool.acquire() as conn:
            # Get current metrics
            row = await conn.fetchrow(
                'SELECT "TrainingMetrics" FROM "TrainedModels" WHERE "Id" = $1',
                model_id
            )
            
            if row:
                current_metrics = json.loads(row["TrainingMetrics"]) if row["TrainingMetrics"] else {}
                current_metrics.update(metrics)
                
                await conn.execute(
                    'UPDATE "TrainedModels" SET "TrainingMetrics" = $1 WHERE "Id" = $2',
                    json.dumps(current_metrics),
                    model_id
                )
    
    async def get_training_status(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get training status for a dataset"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                '''
                SELECT 
                    d."Status" as dataset_status,
                    m."Id" as model_id,
                    m."Status" as model_status,
                    m."TrainingMetrics",
                    m."ErrorMessage"
                FROM "TrainingDatasets" d
                LEFT JOIN "TrainedModels" m ON d."Id" = m."TrainingDatasetId"
                WHERE d."Id" = $1
                ORDER BY m."CreatedAt" DESC
                LIMIT 1
                ''',
                dataset_id
            )
            
            if not row:
                return None
            
            result = {
                "dataset_status": row["dataset_status"],
                "model_id": str(row["model_id"]) if row["model_id"] else None,
                "model_status": row["model_status"],
                "error_message": row["ErrorMessage"]
            }
            
            if row["TrainingMetrics"]:
                result["metrics"] = json.loads(row["TrainingMetrics"])
            
            return result
