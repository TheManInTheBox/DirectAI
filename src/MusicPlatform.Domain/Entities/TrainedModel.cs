using System;

namespace MusicPlatform.Domain.Entities;

/// <summary>
/// Represents a fine-tuned MusicGen model trained on a specific dataset
/// </summary>
public class TrainedModel
{
    public Guid Id { get; set; }
    
    /// <summary>
    /// The dataset this model was trained on
    /// </summary>
    public Guid TrainingDatasetId { get; set; }
    
    /// <summary>
    /// User-friendly name for the model
    /// </summary>
    public string Name { get; set; } = string.Empty;
    
    /// <summary>
    /// Optional description of the model's characteristics
    /// </summary>
    public string? Description { get; set; }
    
    /// <summary>
    /// Blob storage path to the model checkpoint file
    /// </summary>
    public string ModelPath { get; set; } = string.Empty;
    
    /// <summary>
    /// Size of the model file in bytes
    /// </summary>
    public long ModelSizeBytes { get; set; }
    
    /// <summary>
    /// Base model that was fine-tuned (e.g., "facebook/musicgen-melody-large")
    /// </summary>
    public string BaseModel { get; set; } = "facebook/musicgen-melody-large";
    
    /// <summary>
    /// Training configuration and hyperparameters (JSON)
    /// </summary>
    public string TrainingConfig { get; set; } = "{}";
    
    /// <summary>
    /// Training metrics and results (JSON)
    /// - Final loss
    /// - Training duration
    /// - Epochs completed
    /// - Learning rate
    /// - LoRA rank
    /// </summary>
    public string TrainingMetrics { get; set; } = "{}";
    
    /// <summary>
    /// Current status of the model
    /// </summary>
    public TrainedModelStatus Status { get; set; } = TrainedModelStatus.Pending;
    
    /// <summary>
    /// When training started
    /// </summary>
    public DateTime? TrainingStartedAt { get; set; }
    
    /// <summary>
    /// When training completed
    /// </summary>
    public DateTime? TrainingCompletedAt { get; set; }
    
    /// <summary>
    /// When the model was created
    /// </summary>
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    
    /// <summary>
    /// Error message if training failed
    /// </summary>
    public string? ErrorMessage { get; set; }
    
    /// <summary>
    /// Number of times this model has been used for generation
    /// </summary>
    public int UsageCount { get; set; }
    
    /// <summary>
    /// When this model was last used
    /// </summary>
    public DateTime? LastUsedAt { get; set; }
    
    // Navigation properties
    public virtual TrainingDataset TrainingDataset { get; set; } = null!;
}

public enum TrainedModelStatus
{
    /// <summary>
    /// Waiting to start training
    /// </summary>
    Pending,
    
    /// <summary>
    /// Currently training
    /// </summary>
    Training,
    
    /// <summary>
    /// Training completed successfully, model ready to use
    /// </summary>
    Ready,
    
    /// <summary>
    /// Training failed
    /// </summary>
    Failed,
    
    /// <summary>
    /// Model archived/deprecated
    /// </summary>
    Archived
}
