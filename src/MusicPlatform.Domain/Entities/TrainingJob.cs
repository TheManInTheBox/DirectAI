using System;

namespace MusicPlatform.Domain.Entities;

/// <summary>
/// Represents a training job for fine-tuning a MusicGen model
/// </summary>
public class TrainingJob
{
    public Guid Id { get; set; }
    
    /// <summary>
    /// Associated training dataset
    /// </summary>
    public Guid TrainingDatasetId { get; set; }
    public virtual TrainingDataset TrainingDataset { get; set; } = null!;
    
    /// <summary>
    /// Name for the resulting trained model
    /// </summary>
    public string ModelName { get; set; } = string.Empty;
    
    /// <summary>
    /// Base model to fine-tune (e.g., "facebook/MelodyFlow")
    /// </summary>
    public string BaseModel { get; set; } = "facebook/MelodyFlow";
    
    /// <summary>
    /// Current status of the training job
    /// </summary>
    public TrainingJobStatus Status { get; set; } = TrainingJobStatus.Pending;
    
    /// <summary>
    /// Training hyperparameters (JSON)
    /// </summary>
    public string Hyperparameters { get; set; } = "{}";
    
    /// <summary>
    /// Current progress (0-100)
    /// </summary>
    public float Progress { get; set; }
    
    /// <summary>
    /// Current epoch
    /// </summary>
    public int CurrentEpoch { get; set; }
    
    /// <summary>
    /// Total epochs
    /// </summary>
    public int TotalEpochs { get; set; }
    
    /// <summary>
    /// Current training loss
    /// </summary>
    public float? CurrentLoss { get; set; }
    
    /// <summary>
    /// Error message if training failed
    /// </summary>
    public string? ErrorMessage { get; set; }
    
    /// <summary>
    /// When the job was created
    /// </summary>
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    
    /// <summary>
    /// When training started
    /// </summary>
    public DateTime? StartedAt { get; set; }
    
    /// <summary>
    /// When training completed
    /// </summary>
    public DateTime? CompletedAt { get; set; }
    
    /// <summary>
    /// Training duration in seconds
    /// </summary>
    public float? DurationSeconds { get; set; }
    
    /// <summary>
    /// ID of the resulting trained model (if completed)
    /// </summary>
    public Guid? TrainedModelId { get; set; }
    public virtual TrainedModel? TrainedModel { get; set; }
    
    /// <summary>
    /// Additional metadata (JSON)
    /// </summary>
    public string Metadata { get; set; } = "{}";
}

public enum TrainingJobStatus
{
    /// <summary>
    /// Job created, waiting to start
    /// </summary>
    Pending,
    
    /// <summary>
    /// Job queued in Service Bus
    /// </summary>
    Queued,
    
    /// <summary>
    /// Training is running
    /// </summary>
    Running,
    
    /// <summary>
    /// Training completed successfully
    /// </summary>
    Completed,
    
    /// <summary>
    /// Training failed with error
    /// </summary>
    Failed,
    
    /// <summary>
    /// Training was cancelled
    /// </summary>
    Cancelled
}
