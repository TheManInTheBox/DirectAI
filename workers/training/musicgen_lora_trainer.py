"""
MusicGen Fine-Tuning Service with LoRA (Low-Rank Adaptation)
Efficient fine-tuning of MusicGen models on custom datasets using PEFT
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import json
from datetime import datetime

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import (
    MusicgenForConditionalGeneration,
    AutoProcessor,
    TrainingArguments,
    Trainer
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
    PeftModel
)
import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping, LearningRateMonitor
from pytorch_lightning.loggers import TensorBoardLogger

from dataset_preprocessor import MusicGenDataset

logger = logging.getLogger(__name__)


class MusicGenLoRATrainer:
    """
    Trainer for fine-tuning MusicGen with LoRA adapters
    
    Uses Parameter-Efficient Fine-Tuning (PEFT) with LoRA to adapt
    MusicGen to custom musical styles with minimal compute requirements.
    """
    
    def __init__(
        self,
        base_model_name: str = "facebook/musicgen-small",
        lora_r: int = 16,
        lora_alpha: int = 32,
        lora_dropout: float = 0.1,
        target_modules: Optional[list] = None,
        device: str = "auto"
    ):
        """
        Initialize the LoRA trainer
        
        Args:
            base_model_name: Hugging Face model ID for base MusicGen model
            lora_r: LoRA rank (dimensionality of adapter matrices)
            lora_alpha: LoRA scaling factor
            lora_dropout: Dropout probability for LoRA layers
            target_modules: Which modules to apply LoRA to (default: attention layers)
            device: Device to train on ("cuda", "cpu", or "auto")
        """
        self.base_model_name = base_model_name
        self.lora_r = lora_r
        self.lora_alpha = lora_alpha
        self.lora_dropout = lora_dropout
        
        # Default target modules for MusicGen (attention layers)
        if target_modules is None:
            target_modules = [
                "self_attn.q_proj",
                "self_attn.k_proj",
                "self_attn.v_proj",
                "self_attn.out_proj"
            ]
        self.target_modules = target_modules
        
        # Set device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        logger.info(f"Initializing MusicGen LoRA Trainer on device: {self.device}")
        logger.info(f"LoRA config: r={lora_r}, alpha={lora_alpha}, dropout={lora_dropout}")
        
        # Load base model and processor
        self.processor = None
        self.base_model = None
        self.peft_model = None
        
        self._load_base_model()
    
    def _load_base_model(self):
        """Load the base MusicGen model"""
        logger.info(f"Loading base model: {self.base_model_name}")
        
        try:
            self.processor = AutoProcessor.from_pretrained(self.base_model_name)
            self.base_model = MusicgenForConditionalGeneration.from_pretrained(
                self.base_model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            self.base_model.to(self.device)
            
            logger.info("Base model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load base model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")
    
    def prepare_peft_model(self):
        """Prepare model with LoRA adapters"""
        logger.info("Preparing PEFT model with LoRA adapters...")
        
        # Configure LoRA
        lora_config = LoraConfig(
            r=self.lora_r,
            lora_alpha=self.lora_alpha,
            lora_dropout=self.lora_dropout,
            target_modules=self.target_modules,
            bias="none",
            task_type=TaskType.SEQ_2_SEQ_LM
        )
        
        # Apply LoRA to base model
        self.peft_model = get_peft_model(self.base_model, lora_config)
        
        # Print trainable parameters
        self.peft_model.print_trainable_parameters()
        
        logger.info("PEFT model prepared successfully")
        
        return self.peft_model
    
    def train(
        self,
        train_dataset: MusicGenDataset,
        val_dataset: Optional[MusicGenDataset] = None,
        output_dir: Path = Path("./checkpoints"),
        num_epochs: int = 10,
        batch_size: int = 4,
        learning_rate: float = 1e-4,
        gradient_accumulation_steps: int = 4,
        warmup_steps: int = 100,
        logging_steps: int = 10,
        save_steps: int = 500,
        eval_steps: int = 500,
        max_grad_norm: float = 1.0,
        fp16: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Fine-tune MusicGen with LoRA using Hugging Face Trainer
        
        Args:
            train_dataset: Training dataset
            val_dataset: Validation dataset (optional)
            output_dir: Directory to save checkpoints
            num_epochs: Number of training epochs
            batch_size: Batch size per device
            learning_rate: Learning rate
            gradient_accumulation_steps: Steps to accumulate gradients
            warmup_steps: Number of warmup steps
            logging_steps: Log every N steps
            save_steps: Save checkpoint every N steps
            eval_steps: Evaluate every N steps
            max_grad_norm: Maximum gradient norm for clipping
            fp16: Use mixed precision training (FP16)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Training metrics dictionary
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare PEFT model
        if self.peft_model is None:
            self.prepare_peft_model()
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            learning_rate=learning_rate,
            warmup_steps=warmup_steps,
            logging_steps=logging_steps,
            save_steps=save_steps,
            eval_steps=eval_steps if val_dataset else None,
            evaluation_strategy="steps" if val_dataset else "no",
            save_strategy="steps",
            load_best_model_at_end=True if val_dataset else False,
            metric_for_best_model="eval_loss" if val_dataset else None,
            greater_is_better=False,
            fp16=fp16 and self.device == "cuda",
            max_grad_norm=max_grad_norm,
            remove_unused_columns=False,
            dataloader_num_workers=2,
            report_to=["tensorboard"],
            logging_dir=str(output_dir / "logs")
        )
        
        # Create trainer
        trainer = Trainer(
            model=self.peft_model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            tokenizer=self.processor,
            data_collator=self._collate_fn
        )
        
        # Start training
        logger.info("Starting LoRA fine-tuning...")
        logger.info(f"  Num examples: {len(train_dataset)}")
        logger.info(f"  Num epochs: {num_epochs}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Learning rate: {learning_rate}")
        
        try:
            train_result = trainer.train()
            
            # Save final model
            final_model_path = output_dir / "final_model"
            self.save_model(final_model_path)
            
            # Training metrics
            metrics = {
                "train_loss": train_result.training_loss,
                "train_runtime": train_result.metrics["train_runtime"],
                "train_samples_per_second": train_result.metrics["train_samples_per_second"],
                "final_checkpoint": str(final_model_path)
            }
            
            logger.info("Training completed successfully")
            logger.info(f"Final loss: {metrics['train_loss']:.4f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise RuntimeError(f"Training failed: {e}")
    
    def _collate_fn(self, batch):
        """
        Custom collate function for batching
        
        Prepares batches for MusicGen training with text and audio inputs
        """
        # Extract batch components
        input_ids = torch.stack([item["input_ids"] for item in batch])
        attention_mask = torch.stack([item["attention_mask"] for item in batch])
        audio_values = torch.stack([item["audio_values"] for item in batch])
        
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "audio_values": audio_values
        }
    
    def save_model(self, output_path: Path):
        """
        Save LoRA adapters and config
        
        Saves only the LoRA adapter weights (not the full model)
        for efficient storage and deployment
        """
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save PEFT model
        self.peft_model.save_pretrained(str(output_path))
        
        # Save processor
        self.processor.save_pretrained(str(output_path))
        
        # Save training config
        config = {
            "base_model": self.base_model_name,
            "lora_r": self.lora_r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "target_modules": self.target_modules,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(output_path / "training_config.json", 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Model saved to {output_path}")
    
    @staticmethod
    def load_trained_model(
        checkpoint_path: Path,
        base_model_name: str = "facebook/musicgen-small",
        device: str = "auto"
    ) -> PeftModel:
        """
        Load a trained LoRA model from checkpoint
        
        Args:
            checkpoint_path: Path to saved LoRA checkpoint
            base_model_name: Base model to load adapters onto
            device: Device to load model on
            
        Returns:
            Loaded PEFT model with LoRA adapters
        """
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading trained model from {checkpoint_path}")
        
        # Load base model
        base_model = MusicgenForConditionalGeneration.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32
        )
        
        # Load LoRA adapters
        model = PeftModel.from_pretrained(
            base_model,
            str(checkpoint_path),
            is_trainable=False
        )
        model.to(device)
        model.eval()
        
        logger.info("Trained model loaded successfully")
        
        return model


class MusicGenPyTorchLightningModule(pl.LightningModule):
    """
    PyTorch Lightning wrapper for MusicGen LoRA training
    
    Provides advanced training features:
    - Automatic optimization
    - Distributed training support
    - Gradient clipping
    - Learning rate scheduling
    - Checkpoint management
    """
    
    def __init__(
        self,
        peft_model: PeftModel,
        learning_rate: float = 1e-4,
        warmup_steps: int = 100,
        max_steps: int = 10000
    ):
        super().__init__()
        self.model = peft_model
        self.learning_rate = learning_rate
        self.warmup_steps = warmup_steps
        self.max_steps = max_steps
        
        self.save_hyperparameters(ignore=['peft_model'])
    
    def forward(self, input_ids, attention_mask, audio_values):
        """Forward pass"""
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=audio_values  # MusicGen uses audio as labels
        )
        return outputs
    
    def training_step(self, batch, batch_idx):
        """Training step"""
        outputs = self(
            batch["input_ids"],
            batch["attention_mask"],
            batch["audio_values"]
        )
        
        loss = outputs.loss
        
        # Log metrics
        self.log("train_loss", loss, prog_bar=True)
        self.log("learning_rate", self.optimizers().param_groups[0]['lr'])
        
        return loss
    
    def validation_step(self, batch, batch_idx):
        """Validation step"""
        outputs = self(
            batch["input_ids"],
            batch["attention_mask"],
            batch["audio_values"]
        )
        
        loss = outputs.loss
        
        self.log("val_loss", loss, prog_bar=True)
        
        return loss
    
    def configure_optimizers(self):
        """Configure optimizer and learning rate scheduler"""
        optimizer = torch.optim.AdamW(
            self.parameters(),
            lr=self.learning_rate,
            betas=(0.9, 0.999),
            weight_decay=0.01
        )
        
        # Linear warmup + cosine decay
        def lr_lambda(current_step):
            if current_step < self.warmup_steps:
                return float(current_step) / float(max(1, self.warmup_steps))
            progress = float(current_step - self.warmup_steps) / float(max(1, self.max_steps - self.warmup_steps))
            return max(0.0, 0.5 * (1.0 + torch.cos(torch.tensor(progress * 3.14159))))
        
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
        
        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": scheduler,
                "interval": "step",
                "frequency": 1
            }
        }


def train_with_pytorch_lightning(
    peft_model: PeftModel,
    train_dataloader: DataLoader,
    val_dataloader: Optional[DataLoader],
    output_dir: Path,
    max_epochs: int = 10,
    learning_rate: float = 1e-4,
    accelerator: str = "auto",
    devices: int = 1,
    precision: str = "16-mixed"
) -> Dict[str, Any]:
    """
    Train MusicGen with PyTorch Lightning
    
    Provides more advanced training capabilities than Hugging Face Trainer:
    - Multi-GPU support
    - Gradient accumulation
    - Advanced callbacks
    - Better logging
    
    Args:
        peft_model: PEFT model with LoRA adapters
        train_dataloader: Training dataloader
        val_dataloader: Validation dataloader
        output_dir: Output directory for checkpoints
        max_epochs: Maximum number of epochs
        learning_rate: Learning rate
        accelerator: Accelerator type ("gpu", "cpu", or "auto")
        devices: Number of devices to use
        precision: Training precision ("32", "16-mixed", or "bf16-mixed")
        
    Returns:
        Training metrics
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Calculate max steps
    max_steps = len(train_dataloader) * max_epochs
    
    # Create Lightning module
    lit_module = MusicGenPyTorchLightningModule(
        peft_model=peft_model,
        learning_rate=learning_rate,
        warmup_steps=min(100, max_steps // 10),
        max_steps=max_steps
    )
    
    # Callbacks
    checkpoint_callback = ModelCheckpoint(
        dirpath=output_dir / "checkpoints",
        filename="musicgen-lora-{epoch:02d}-{val_loss:.4f}",
        save_top_k=3,
        monitor="val_loss",
        mode="min",
        save_last=True
    )
    
    early_stop_callback = EarlyStopping(
        monitor="val_loss",
        patience=3,
        mode="min"
    )
    
    lr_monitor = LearningRateMonitor(logging_interval='step')
    
    # Logger
    tb_logger = TensorBoardLogger(
        save_dir=output_dir / "logs",
        name="musicgen_lora"
    )
    
    # Trainer
    trainer = pl.Trainer(
        default_root_dir=str(output_dir),
        accelerator=accelerator,
        devices=devices,
        precision=precision,
        max_epochs=max_epochs,
        callbacks=[checkpoint_callback, early_stop_callback, lr_monitor],
        logger=tb_logger,
        gradient_clip_val=1.0,
        accumulate_grad_batches=4,
        log_every_n_steps=10,
        val_check_interval=0.25,
        enable_progress_bar=True
    )
    
    # Train
    logger.info("Starting PyTorch Lightning training...")
    trainer.fit(lit_module, train_dataloader, val_dataloader)
    
    # Return metrics
    metrics = {
        "best_checkpoint": checkpoint_callback.best_model_path,
        "best_val_loss": checkpoint_callback.best_model_score.item(),
        "total_epochs": trainer.current_epoch
    }
    
    logger.info(f"Training complete. Best checkpoint: {metrics['best_checkpoint']}")
    
    return metrics


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize trainer
    trainer = MusicGenLoRATrainer(
        base_model_name="facebook/musicgen-small",
        lora_r=16,
        lora_alpha=32
    )
    
    # Load dataset (example)
    # dataset = MusicGenDataset.from_directory(...)
    # trainer.train(dataset, output_dir=Path("./checkpoints"))
    
    print("MusicGen LoRA Trainer initialized successfully")
