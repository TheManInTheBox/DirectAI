using System;
using MusicPlatform.Domain.Models;

namespace MusicPlatform.Domain.Entities;

/// <summary>
/// Links a stem to a training dataset with weighting information
/// </summary>
public class TrainingDatasetStem
{
    public Guid Id { get; set; }
    
    /// <summary>
    /// The training dataset this stem belongs to
    /// </summary>
    public Guid TrainingDatasetId { get; set; }
    
    /// <summary>
    /// The stem to include in training
    /// </summary>
    public Guid StemId { get; set; }
    
    /// <summary>
    /// Weight/influence of this stem in training (0.0 to 1.0)
    /// Higher values mean more influence on the trained model
    /// </summary>
    public float Weight { get; set; } = 1.0f;
    
    /// <summary>
    /// Order of this stem in the dataset (for display/processing)
    /// </summary>
    public int Order { get; set; }
    
    /// <summary>
    /// When this stem was added to the dataset
    /// </summary>
    public DateTime AddedAt { get; set; } = DateTime.UtcNow;
    
    /// <summary>
    /// Optional notes about why this stem was selected
    /// </summary>
    public string? Notes { get; set; }
    
    // Navigation properties
    public virtual TrainingDataset TrainingDataset { get; set; } = null!;
    public virtual Stem Stem { get; set; } = null!;
}
