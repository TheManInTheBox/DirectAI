import os
import logging
import time
import tempfile
import torch
import torchaudio
from typing import Dict, Any, List, Optional
from transformers import AutoProcessor, MusicgenForConditionalGeneration
from peft import LoraConfig, get_peft_model, TaskType
from torch.optim import AdamW
from torch.utils.data import Dataset, DataLoader
import librosa
import numpy as np

logger = logging.getLogger(__name__)

class AudioDataset(Dataset):
    """Dataset for loading audio stems for training"""
    
    def __init__(self, audio_files: List[str], processor, sample_rate: int = 32000, max_duration: float = 30.0):
        self.audio_files = audio_files
        self.processor = processor
        self.sample_rate = sample_rate
        self.max_duration = max_duration
        self.max_samples = int(sample_rate * max_duration)
        
    def __len__(self):
        return len(self.audio_files)
    
    def __getitem__(self, idx):
        audio_path = self.audio_files[idx]
        
        # Load audio
        audio, sr = librosa.load(audio_path, sr=self.sample_rate, mono=True)
        
        # Truncate or pad to max_duration
        if len(audio) > self.max_samples:
            # Random crop during training
            start = np.random.randint(0, len(audio) - self.max_samples)
            audio = audio[start:start + self.max_samples]
        else:
            # Pad with silence
            audio = np.pad(audio, (0, self.max_samples - len(audio)), mode='constant')
        
        # Convert to tensor
        audio_tensor = torch.from_numpy(audio).float().unsqueeze(0)  # (1, samples)
        
        return audio_tensor

class MusicGenTrainingService:
    """Service for fine-tuning MusicGen models with LoRA"""
    
    def __init__(self, storage_service, db_service, use_gpu: bool = True):
        self.storage_service = storage_service
        self.db_service = db_service
        self.use_gpu = use_gpu
        self.device = None
        self.processor = None
        self.base_model = None
        self.is_initialized = False
        self.sample_rate = 32000
        
    async def initialize(self):
        """Initialize the training service"""
        logger.info("Initializing MusicGen training service...")
        
        # Set device
        if self.use_gpu and torch.cuda.is_available():
            self.device = "cuda"
            logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = "cpu"
            logger.info("Using CPU (training will be slow)")
        
        # Load base model and processor
        logger.info("Loading MusicGen-melody-large base model...")
        model_name = "facebook/musicgen-melody-large"
        
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.base_model = MusicgenForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        )
        
        # Don't move base model to device yet - we'll do this per training job
        logger.info(f"Base model loaded successfully")
        
        self.is_initialized = True
        logger.info("Training service initialization complete")
    
    async def train_model(
        self,
        dataset_id: str,
        model_name: str,
        epochs: int = 100,
        learning_rate: float = 1e-4,
        lora_rank: int = 8,
        lora_alpha: int = 16,
        batch_size: int = 1
    ) -> Dict[str, Any]:
        """Fine-tune MusicGen on a training dataset"""
        
        start_time = time.time()
        
        try:
            # 1. Fetch dataset from database
            logger.info(f"Fetching training dataset {dataset_id}...")
            dataset_info = await self.db_service.get_training_dataset(dataset_id)
            
            if not dataset_info:
                raise ValueError(f"Dataset {dataset_id} not found")
            
            if not dataset_info.get('stems'):
                raise ValueError(f"Dataset {dataset_id} has no stems")
            
            # 2. Create trained model record
            model_id = await self.db_service.create_trained_model(
                dataset_id=dataset_id,
                name=model_name,
                base_model="facebook/musicgen-melody-large"
            )
            
            # Update status to Training
            await self.db_service.update_training_dataset_status(dataset_id, "Training")
            await self.db_service.update_trained_model_status(model_id, "Training")
            
            # 3. Download audio files
            logger.info(f"Downloading {len(dataset_info['stems'])} audio files...")
            audio_files = []
            
            with tempfile.TemporaryDirectory() as temp_dir:
                for stem in dataset_info['stems']:
                    blob_path = stem['blob_path']
                    local_path = os.path.join(temp_dir, f"{stem['id']}.wav")
                    
                    await self.storage_service.download_blob(blob_path, local_path)
                    audio_files.append(local_path)
                    logger.info(f"Downloaded {blob_path}")
                
                # 4. Create dataset and dataloader
                logger.info("Creating training dataset...")
                train_dataset = AudioDataset(
                    audio_files=audio_files,
                    processor=self.processor,
                    sample_rate=self.sample_rate,
                    max_duration=30.0  # 30-second chunks
                )
                
                train_loader = DataLoader(
                    train_dataset,
                    batch_size=batch_size,
                    shuffle=True,
                    num_workers=0  # Single worker for audio loading
                )
                
                # 5. Configure LoRA
                logger.info("Configuring LoRA...")
                lora_config = LoraConfig(
                    task_type=TaskType.CAUSAL_LM,
                    r=lora_rank,
                    lora_alpha=lora_alpha,
                    lora_dropout=0.1,
                    target_modules=["q_proj", "v_proj"]  # Target attention layers
                )
                
                # Create LoRA model
                model = get_peft_model(self.base_model, lora_config)
                model.to(self.device)
                model.train()
                
                logger.info(f"Trainable parameters: {model.num_parameters(only_trainable=True):,}")
                
                # 6. Setup optimizer
                optimizer = AdamW(model.parameters(), lr=learning_rate)
                
                # 7. Training loop
                logger.info(f"Starting training for {epochs} epochs...")
                total_loss = 0
                num_batches = 0
                
                for epoch in range(epochs):
                    epoch_loss = 0
                    
                    for batch_idx, audio_batch in enumerate(train_loader):
                        audio_batch = audio_batch.to(self.device)
                        
                        # Forward pass
                        outputs = model(input_values=audio_batch, labels=audio_batch)
                        loss = outputs.loss
                        
                        # Backward pass
                        optimizer.zero_grad()
                        loss.backward()
                        optimizer.step()
                        
                        epoch_loss += loss.item()
                        total_loss += loss.item()
                        num_batches += 1
                        
                        if batch_idx % 10 == 0:
                            logger.info(f"Epoch {epoch+1}/{epochs}, Batch {batch_idx}, Loss: {loss.item():.4f}")
                    
                    avg_epoch_loss = epoch_loss / len(train_loader)
                    logger.info(f"Epoch {epoch+1} complete. Average loss: {avg_epoch_loss:.4f}")
                    
                    # Update metrics in database
                    await self.db_service.update_training_metrics(
                        model_id,
                        {
                            "current_epoch": epoch + 1,
                            "total_epochs": epochs,
                            "current_loss": avg_epoch_loss,
                            "average_loss": total_loss / num_batches
                        }
                    )
                
                # 8. Save LoRA checkpoint
                logger.info("Saving LoRA checkpoint...")
                checkpoint_dir = os.path.join(temp_dir, "checkpoint")
                os.makedirs(checkpoint_dir, exist_ok=True)
                
                # Save LoRA adapters only (small ~50MB)
                model.save_pretrained(checkpoint_dir)
                self.processor.save_pretrained(checkpoint_dir)
                
                # 9. Upload to blob storage
                logger.info("Uploading checkpoint to blob storage...")
                checkpoint_blob_path = f"models/{model_id}/checkpoint"
                
                # Zip checkpoint directory
                import shutil
                checkpoint_zip = os.path.join(temp_dir, "checkpoint.zip")
                shutil.make_archive(
                    checkpoint_zip.replace('.zip', ''),
                    'zip',
                    checkpoint_dir
                )
                
                await self.storage_service.upload_blob(
                    checkpoint_zip,
                    checkpoint_blob_path + ".zip"
                )
                
                checkpoint_size = os.path.getsize(checkpoint_zip)
                logger.info(f"Checkpoint uploaded ({checkpoint_size / 1024 / 1024:.2f} MB)")
                
                # 10. Update database records
                training_time = time.time() - start_time
                final_loss = total_loss / num_batches if num_batches > 0 else 0
                
                await self.db_service.update_trained_model(
                    model_id=model_id,
                    model_path=checkpoint_blob_path + ".zip",
                    model_size_bytes=checkpoint_size,
                    training_config={
                        "epochs": epochs,
                        "learning_rate": learning_rate,
                        "lora_rank": lora_rank,
                        "lora_alpha": lora_alpha,
                        "batch_size": batch_size
                    },
                    training_metrics={
                        "final_loss": final_loss,
                        "average_loss": total_loss / num_batches,
                        "training_time_seconds": training_time,
                        "num_stems": len(audio_files)
                    },
                    status="Ready"
                )
                
                await self.db_service.update_training_dataset_status(dataset_id, "Completed")
                
                logger.info(f"Training complete! Model {model_id} ready in {training_time:.1f}s")
                
                return {
                    "model_id": model_id,
                    "model_path": checkpoint_blob_path + ".zip",
                    "training_time": training_time,
                    "final_loss": final_loss
                }
        
        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            
            # Update status to Failed
            if 'model_id' in locals():
                await self.db_service.update_trained_model_status(
                    model_id,
                    "Failed",
                    error_message=str(e)
                )
            
            await self.db_service.update_training_dataset_status(dataset_id, "Draft")
            
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up training service...")
        
        # Clear models from GPU
        if self.base_model:
            del self.base_model
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        self.is_initialized = False
