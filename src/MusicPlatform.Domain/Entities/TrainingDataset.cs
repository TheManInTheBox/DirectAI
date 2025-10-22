using System;
using System.Collections.Generic;

namespace MusicPlatform.Domain.Entities;

/// <summary>
/// Represents a collection of selected stems used for training a custom model
/// </summary>
public class TrainingDataset
{
    public Guid Id { get; set; }
    
    /// <summary>
    /// User-friendly name for the dataset (e.g., "My Rock Style", "Jazz Fusion Mix")
    /// </summary>
    public string Name { get; set; } = string.Empty;
    
    /// <summary>
    /// Optional description of the training dataset
    /// </summary>
    public string? Description { get; set; }
    
    /// <summary>
    /// Current status of the dataset
    /// </summary>
    public TrainingDatasetStatus Status { get; set; } = TrainingDatasetStatus.Draft;
    
    /// <summary>
    /// When the dataset was created
    /// </summary>
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    
    /// <summary>
    /// When the dataset was last modified
    /// </summary>
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    
    /// <summary>
    /// Total duration of all stems in seconds
    /// </summary>
    public float TotalDurationSeconds { get; set; }
    
    /// <summary>
    /// Number of stems in the dataset
    /// </summary>
    public int StemCount { get; set; }
    
    /// <summary>
    /// Additional metadata (JSON)
    /// </summary>
    public string Metadata { get; set; } = "{}";
    
    // Navigation properties
    public virtual ICollection<TrainingDatasetStem> Stems { get; set; } = new List<TrainingDatasetStem>();
    public virtual ICollection<TrainedModel> TrainedModels { get; set; } = new List<TrainedModel>();
}

public enum TrainingDatasetStatus
{
    /// <summary>
    /// Dataset is being created, stems being added
    /// </summary>
    Draft,
    
    /// <summary>
    /// Dataset is complete and ready for training
    /// </summary>
    Ready,
    
    /// <summary>
    /// Dataset is currently being used for training
    /// </summary>
    Training,
    
    /// <summary>
    /// Training completed, model available
    /// </summary>
    Completed,
    
    /// <summary>
    /// Dataset archived/no longer active
    /// </summary>
    Archived
}
