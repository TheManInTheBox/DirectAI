using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Entities;
using MusicPlatform.Infrastructure.Data;
using System.Text.Json;
using Azure.Messaging.ServiceBus;

namespace MusicPlatform.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class TrainingController : ControllerBase
{
    private readonly MusicPlatformDbContext _context;
    private readonly ILogger<TrainingController> _logger;
    private readonly ServiceBusSender? _trainingJobSender;

    public TrainingController(
        MusicPlatformDbContext context,
        ILogger<TrainingController> logger,
        ServiceBusClient? serviceBusClient = null)
    {
        _context = context;
        _logger = logger;
        
        // Initialize Service Bus sender if client is available
        if (serviceBusClient != null)
        {
            var queueName = Environment.GetEnvironmentVariable("TRAINING_QUEUE_NAME") ?? "training-jobs";
            _trainingJobSender = serviceBusClient.CreateSender(queueName);
        }
    }

    // Dataset Management

    [HttpPost("datasets")]
    public async Task<IActionResult> CreateDataset([FromBody] CreateDatasetRequest request)
    {
        var dataset = new TrainingDataset
        {
            Id = Guid.NewGuid(),
            Name = request.Name,
            Description = request.Description,
            Status = TrainingDatasetStatus.Draft,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow,
            TotalDurationSeconds = 0,
            StemCount = 0,
            Metadata = "{}"
        };

        _context.TrainingDatasets.Add(dataset);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Created training dataset {DatasetId} '{Name}'", dataset.Id, dataset.Name);

        return Ok(new
        {
            id = dataset.Id,
            name = dataset.Name,
            description = dataset.Description,
            status = dataset.Status.ToString(),
            createdAt = dataset.CreatedAt,
            stemCount = dataset.StemCount,
            totalDurationSeconds = dataset.TotalDurationSeconds
        });
    }

    [HttpGet("datasets")]
    public async Task<IActionResult> ListDatasets(
        [FromQuery] string? status = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
    {
        var query = _context.TrainingDatasets.AsQueryable();

        if (!string.IsNullOrEmpty(status) && Enum.TryParse<TrainingDatasetStatus>(status, true, out var statusEnum))
        {
            query = query.Where(d => d.Status == statusEnum);
        }

        var total = await query.CountAsync();
        var datasets = await query
            .OrderByDescending(d => d.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(d => new
            {
                id = d.Id,
                name = d.Name,
                description = d.Description,
                status = d.Status.ToString(),
                createdAt = d.CreatedAt,
                updatedAt = d.UpdatedAt,
                stemCount = d.StemCount,
                totalDurationSeconds = d.TotalDurationSeconds
            })
            .ToListAsync();

        return Ok(new
        {
            total,
            page,
            pageSize,
            datasets
        });
    }

    [HttpGet("datasets/{id}")]
    public async Task<IActionResult> GetDataset(Guid id)
    {
        var dataset = await _context.TrainingDatasets
            .Include(d => d.Stems)
                .ThenInclude(ds => ds.Stem)
            .Include(d => d.TrainedModels)
            .FirstOrDefaultAsync(d => d.Id == id);

        if (dataset == null)
            return NotFound();

        return Ok(new
        {
            id = dataset.Id,
            name = dataset.Name,
            description = dataset.Description,
            status = dataset.Status.ToString(),
            createdAt = dataset.CreatedAt,
            updatedAt = dataset.UpdatedAt,
            stemCount = dataset.StemCount,
            totalDurationSeconds = dataset.TotalDurationSeconds,
            metadata = JsonSerializer.Deserialize<object>(dataset.Metadata),
            stems = dataset.Stems.OrderBy(s => s.Order).Select(s => new
            {
                id = s.Id,
                stemId = s.StemId,
                stemType = s.Stem.Type,
                weight = s.Weight,
                order = s.Order,
                notes = s.Notes,
                addedAt = s.AddedAt
            }),
            trainedModels = dataset.TrainedModels.Select(m => new
            {
                id = m.Id,
                name = m.Name,
                status = m.Status.ToString(),
                createdAt = m.CreatedAt
            })
        });
    }

    [HttpPut("datasets/{id}")]
    public async Task<IActionResult> UpdateDataset(Guid id, [FromBody] UpdateDatasetRequest request)
    {
        var dataset = await _context.TrainingDatasets.FindAsync(id);
        if (dataset == null)
            return NotFound();

        if (!string.IsNullOrEmpty(request.Name))
            dataset.Name = request.Name;

        if (request.Description != null)
            dataset.Description = request.Description;

        if (request.Status.HasValue)
        {
            // Validate status transitions
            if (dataset.Status == TrainingDatasetStatus.Training && request.Status != TrainingDatasetStatus.Training)
            {
                return BadRequest("Cannot change status while training is in progress");
            }
            dataset.Status = request.Status.Value;
        }

        dataset.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        return NoContent();
    }

    [HttpDelete("datasets/{id}")]
    public async Task<IActionResult> DeleteDataset(Guid id)
    {
        var dataset = await _context.TrainingDatasets.FindAsync(id);
        if (dataset == null)
            return NotFound();

        if (dataset.Status == TrainingDatasetStatus.Training)
            return BadRequest("Cannot delete dataset while training is in progress");

        _context.TrainingDatasets.Remove(dataset);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Deleted training dataset {DatasetId}", id);

        return NoContent();
    }

    // Stem Management

    [HttpPost("datasets/{datasetId}/stems")]
    public async Task<IActionResult> AddStem(Guid datasetId, [FromBody] AddStemRequest request)
    {
        var dataset = await _context.TrainingDatasets
            .Include(d => d.Stems)
            .FirstOrDefaultAsync(d => d.Id == datasetId);

        if (dataset == null)
            return NotFound("Dataset not found");

        if (dataset.Status != TrainingDatasetStatus.Draft)
            return BadRequest("Can only add stems to datasets in Draft status");

        var stem = await _context.Stems.FindAsync(request.StemId);
        if (stem == null)
            return NotFound("Stem not found");

        // Check if already added
        if (dataset.Stems.Any(s => s.StemId == request.StemId))
            return BadRequest("Stem already in dataset");

        var datasetStem = new TrainingDatasetStem
        {
            Id = Guid.NewGuid(),
            TrainingDatasetId = datasetId,
            StemId = request.StemId,
            Weight = request.Weight ?? 1.0f,
            Order = dataset.Stems.Count,
            AddedAt = DateTime.UtcNow,
            Notes = request.Notes
        };

        _context.TrainingDatasetStems.Add(datasetStem);

        // Update dataset stats
        dataset.StemCount = dataset.Stems.Count + 1;
        dataset.TotalDurationSeconds += stem.DurationSeconds;
        dataset.UpdatedAt = DateTime.UtcNow;

        await _context.SaveChangesAsync();

        _logger.LogInformation("Added stem {StemId} to dataset {DatasetId}", request.StemId, datasetId);

        return Ok(new
        {
            id = datasetStem.Id,
            stemId = datasetStem.StemId,
            weight = datasetStem.Weight,
            order = datasetStem.Order,
            addedAt = datasetStem.AddedAt
        });
    }

    [HttpPut("datasets/{datasetId}/stems/{stemId}")]
    public async Task<IActionResult> UpdateStem(
        Guid datasetId,
        Guid stemId,
        [FromBody] UpdateStemRequest request)
    {
        var datasetStem = await _context.TrainingDatasetStems
            .Include(ds => ds.TrainingDataset)
            .FirstOrDefaultAsync(ds => ds.TrainingDatasetId == datasetId && ds.StemId == stemId);

        if (datasetStem == null)
            return NotFound();

        if (datasetStem.TrainingDataset.Status != TrainingDatasetStatus.Draft)
            return BadRequest("Can only modify stems in datasets with Draft status");

        if (request.Weight.HasValue)
            datasetStem.Weight = request.Weight.Value;

        if (request.Notes != null)
            datasetStem.Notes = request.Notes;

        datasetStem.TrainingDataset.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        return NoContent();
    }

    [HttpDelete("datasets/{datasetId}/stems/{stemId}")]
    public async Task<IActionResult> RemoveStem(Guid datasetId, Guid stemId)
    {
        var datasetStem = await _context.TrainingDatasetStems
            .Include(ds => ds.TrainingDataset)
            .Include(ds => ds.Stem)
            .FirstOrDefaultAsync(ds => ds.TrainingDatasetId == datasetId && ds.StemId == stemId);

        if (datasetStem == null)
            return NotFound();

        if (datasetStem.TrainingDataset.Status != TrainingDatasetStatus.Draft)
            return BadRequest("Can only remove stems from datasets in Draft status");

        _context.TrainingDatasetStems.Remove(datasetStem);

        // Update dataset stats
        datasetStem.TrainingDataset.StemCount--;
        datasetStem.TrainingDataset.TotalDurationSeconds -= datasetStem.Stem.DurationSeconds;
        datasetStem.TrainingDataset.UpdatedAt = DateTime.UtcNow;

        await _context.SaveChangesAsync();

        _logger.LogInformation("Removed stem {StemId} from dataset {DatasetId}", stemId, datasetId);

        return NoContent();
    }

    // Trained Model Management

    [HttpGet("models")]
    public async Task<IActionResult> ListModels(
        [FromQuery] string? status = null,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
    {
        var query = _context.TrainedModels.AsQueryable();

        if (!string.IsNullOrEmpty(status) && Enum.TryParse<TrainedModelStatus>(status, true, out var statusEnum))
        {
            query = query.Where(m => m.Status == statusEnum);
        }

        var total = await query.CountAsync();
        var models = await query
            .OrderByDescending(m => m.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(m => new
            {
                id = m.Id,
                name = m.Name,
                description = m.Description,
                status = m.Status.ToString(),
                baseModel = m.BaseModel,
                modelSizeBytes = m.ModelSizeBytes,
                trainingDatasetId = m.TrainingDatasetId,
                createdAt = m.CreatedAt,
                trainingStartedAt = m.TrainingStartedAt,
                trainingCompletedAt = m.TrainingCompletedAt,
                usageCount = m.UsageCount,
                lastUsedAt = m.LastUsedAt
            })
            .ToListAsync();

        return Ok(new
        {
            total,
            page,
            pageSize,
            models
        });
    }

    [HttpGet("models/{id}")]
    public async Task<IActionResult> GetModel(Guid id)
    {
        var model = await _context.TrainedModels
            .Include(m => m.TrainingDataset)
            .FirstOrDefaultAsync(m => m.Id == id);

        if (model == null)
            return NotFound();

        return Ok(new
        {
            id = model.Id,
            name = model.Name,
            description = model.Description,
            status = model.Status.ToString(),
            baseModel = model.BaseModel,
            modelPath = model.ModelPath,
            modelSizeBytes = model.ModelSizeBytes,
            trainingDatasetId = model.TrainingDatasetId,
            trainingDatasetName = model.TrainingDataset.Name,
            trainingConfig = JsonSerializer.Deserialize<object>(model.TrainingConfig),
            trainingMetrics = JsonSerializer.Deserialize<object>(model.TrainingMetrics),
            createdAt = model.CreatedAt,
            trainingStartedAt = model.TrainingStartedAt,
            trainingCompletedAt = model.TrainingCompletedAt,
            usageCount = model.UsageCount,
            lastUsedAt = model.LastUsedAt,
            errorMessage = model.ErrorMessage
        });
    }
    
    // Training Operations
    
    // Legacy HTTP-based training endpoint (deprecated in favor of job-based system)
    [HttpPost("train")]
    public async Task<IActionResult> StartTraining([FromBody] StartTrainingRequest request)
    {
        // Validate dataset exists and is ready
        var dataset = await _context.TrainingDatasets
            .Include(d => d.Stems)
            .FirstOrDefaultAsync(d => d.Id == request.DatasetId);
        
        if (dataset == null)
            return NotFound("Dataset not found");
        
        if (dataset.Status != TrainingDatasetStatus.Ready && dataset.Status != TrainingDatasetStatus.Draft)
            return BadRequest($"Dataset must be in Ready or Draft status (current: {dataset.Status})");
        
        if (dataset.Stems.Count == 0)
            return BadRequest("Dataset has no stems");
        
        // Update dataset to Ready status if Draft
        if (dataset.Status == TrainingDatasetStatus.Draft)
        {
            dataset.Status = TrainingDatasetStatus.Ready;
            dataset.UpdatedAt = DateTime.UtcNow;
            await _context.SaveChangesAsync();
        }
        
        // Call training worker
        using var httpClient = new HttpClient();
        var trainingWorkerUrl = Environment.GetEnvironmentVariable("TRAINING_WORKER_URL") 
            ?? "http://training-worker:8003";
        
        var trainingRequest = new
        {
            dataset_id = request.DatasetId.ToString(),
            model_name = request.ModelName,
            epochs = request.Epochs ?? 100,
            learning_rate = request.LearningRate ?? 1e-4f,
            lora_rank = request.LoraRank ?? 8,
            lora_alpha = request.LoraAlpha ?? 16,
            batch_size = request.BatchSize ?? 1
        };
        
        try
        {
            var response = await httpClient.PostAsJsonAsync(
                $"{trainingWorkerUrl}/train",
                trainingRequest
            );
            
            if (!response.IsSuccessStatusCode)
            {
                var error = await response.Content.ReadAsStringAsync();
                _logger.LogError("Training worker returned error: {Error}", error);
                return StatusCode((int)response.StatusCode, $"Training worker error: {error}");
            }
            
            var result = await response.Content.ReadFromJsonAsync<Dictionary<string, object>>();
            
            _logger.LogInformation(
                "Started training for dataset {DatasetId}, model will be {ModelId}",
                request.DatasetId,
                result?["model_id"]
            );
            
            return Accepted(new
            {
                message = "Training started",
                datasetId = request.DatasetId,
                modelId = result?["model_id"],
                trainingWorkerUrl = trainingWorkerUrl
            });
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Failed to connect to training worker at {Url}", trainingWorkerUrl);
            return StatusCode(503, $"Training worker unavailable: {ex.Message}");
        }
    }
    
    // New Queue-Based Training Job System
    
    /// <summary>
    /// Get all training jobs
    /// </summary>
    [HttpGet("jobs")]
    public async Task<ActionResult<IEnumerable<TrainingJobDto>>> GetTrainingJobs()
    {
        var jobs = await _context.TrainingJobs
            .Include(j => j.TrainingDataset)
            .Include(j => j.TrainedModel)
            .OrderByDescending(j => j.CreatedAt)
            .Select(j => MapToDto(j))
            .ToListAsync();

        return Ok(jobs);
    }

    /// <summary>
    /// Get a specific training job by ID
    /// </summary>
    [HttpGet("jobs/{id}")]
    public async Task<ActionResult<TrainingJobDto>> GetTrainingJob(Guid id)
    {
        var job = await _context.TrainingJobs
            .Include(j => j.TrainingDataset)
            .Include(j => j.TrainedModel)
            .FirstOrDefaultAsync(j => j.Id == id);

        if (job == null)
        {
            return NotFound();
        }

        return Ok(MapToDto(job));
    }

    /// <summary>
    /// Create and queue a new training job
    /// </summary>
    [HttpPost("jobs")]
    public async Task<ActionResult<TrainingJobDto>> CreateTrainingJob([FromBody] CreateTrainingJobRequest request)
    {
        // Validate dataset exists and is ready
        var dataset = await _context.TrainingDatasets
            .FirstOrDefaultAsync(d => d.Id == request.DatasetId);

        if (dataset == null)
        {
            return NotFound($"Training dataset {request.DatasetId} not found");
        }

        if (dataset.Status != TrainingDatasetStatus.Ready)
        {
            return BadRequest($"Dataset must be in Ready status. Current status: {dataset.Status}");
        }

        // Create training job
        var job = new TrainingJob
        {
            Id = Guid.NewGuid(),
            TrainingDatasetId = request.DatasetId,
            ModelName = request.ModelName,
            BaseModel = request.BaseModel ?? "facebook/MelodyFlow",
            Status = TrainingJobStatus.Pending,
            TotalEpochs = request.Epochs ?? 100,
            Hyperparameters = JsonSerializer.Serialize(new
            {
                learning_rate = request.LearningRate ?? 1e-4f,
                lora_rank = request.LoraRank ?? 8,
                lora_alpha = request.LoraAlpha ?? 16,
                batch_size = request.BatchSize ?? 1
            }),
            CreatedAt = DateTime.UtcNow
        };

        _context.TrainingJobs.Add(job);
        await _context.SaveChangesAsync();

        // Queue the training job in Service Bus
        if (_trainingJobSender != null)
        {
            try
            {
                var message = new ServiceBusMessage(JsonSerializer.Serialize(new
                {
                    job_id = job.Id.ToString(),
                    dataset_id = dataset.Id.ToString(),
                    model_name = request.ModelName,
                    base_model = job.BaseModel,
                    epochs = request.Epochs ?? 100,
                    learning_rate = request.LearningRate ?? 1e-4f,
                    lora_rank = request.LoraRank ?? 8,
                    lora_alpha = request.LoraAlpha ?? 16,
                    batch_size = request.BatchSize ?? 1,
                    callback_url = $"{Request.Scheme}://{Request.Host}/api/training/callback"
                }));

                await _trainingJobSender.SendMessageAsync(message);

                // Update job status to queued
                job.Status = TrainingJobStatus.Queued;
                await _context.SaveChangesAsync();

                _logger.LogInformation($"Training job {job.Id} queued successfully");
            }
            catch (Exception ex)
            {
                _logger.LogError($"Failed to queue training job: {ex.Message}");
                // Keep job in Pending status if queuing fails
            }
        }
        else
        {
            _logger.LogWarning("Service Bus client not configured, job will remain in Pending status");
        }

        return CreatedAtAction(nameof(GetTrainingJob), new { id = job.Id }, MapToDto(job));
    }

    /// <summary>
    /// Callback endpoint for training worker to update job status
    /// </summary>
    [HttpPost("callback")]
    public async Task<IActionResult> TrainingCallback([FromBody] TrainingCallbackRequest request)
    {
        var job = await _context.TrainingJobs.FirstOrDefaultAsync(j => j.Id == Guid.Parse(request.JobId));

        if (job == null)
        {
            return NotFound();
        }

        job.Status = request.Status switch
        {
            "completed" => TrainingJobStatus.Completed,
            "failed" => TrainingJobStatus.Failed,
            "running" => TrainingJobStatus.Running,
            _ => job.Status
        };

        if (request.Status == "running" && job.StartedAt == null)
        {
            job.StartedAt = DateTime.UtcNow;
        }

        if (request.Status == "completed" && !string.IsNullOrEmpty(request.ModelPath))
        {
            // Create trained model record
            var trainedModel = new TrainedModel
            {
                Id = Guid.NewGuid(),
                Name = job.ModelName,
                TrainingDatasetId = job.TrainingDatasetId,
                ModelPath = request.ModelPath,
                BaseModel = job.BaseModel,
                Status = TrainedModelStatus.Ready,
                TrainingConfig = job.Hyperparameters,
                TrainingMetrics = JsonSerializer.Serialize(new
                {
                    final_loss = request.FinalLoss,
                    training_time = request.TrainingTime
                }),
                CreatedAt = DateTime.UtcNow,
                TrainingStartedAt = job.StartedAt,
                TrainingCompletedAt = DateTime.UtcNow
            };

            _context.TrainedModels.Add(trainedModel);
            job.TrainedModelId = trainedModel.Id;
        }

        if (request.Status == "failed")
        {
            job.ErrorMessage = request.ErrorMessage;
        }

        if (request.Status == "completed" || request.Status == "failed")
        {
            job.CompletedAt = DateTime.UtcNow;
            job.DurationSeconds = request.TrainingTime;
        }

        await _context.SaveChangesAsync();

        _logger.LogInformation($"Updated training job {job.Id} to status {request.Status}");

        return Ok();
    }

    /// <summary>
    /// Cancel a training job
    /// </summary>
    [HttpPost("jobs/{id}/cancel")]
    public async Task<IActionResult> CancelTrainingJob(Guid id)
    {
        var job = await _context.TrainingJobs.FirstOrDefaultAsync(j => j.Id == id);

        if (job == null)
        {
            return NotFound();
        }

        if (job.Status == TrainingJobStatus.Completed || job.Status == TrainingJobStatus.Failed)
        {
            return BadRequest("Cannot cancel a completed or failed job");
        }

        job.Status = TrainingJobStatus.Cancelled;
        job.CompletedAt = DateTime.UtcNow;

        await _context.SaveChangesAsync();

        _logger.LogInformation($"Cancelled training job {id}");

        return Ok();
    }

    private static TrainingJobDto MapToDto(TrainingJob job)
    {
        return new TrainingJobDto
        {
            Id = job.Id,
            DatasetId = job.TrainingDatasetId,
            DatasetName = job.TrainingDataset?.Name,
            ModelName = job.ModelName,
            BaseModel = job.BaseModel,
            Status = job.Status.ToString(),
            Progress = job.Progress,
            CurrentEpoch = job.CurrentEpoch,
            TotalEpochs = job.TotalEpochs,
            CurrentLoss = job.CurrentLoss,
            ErrorMessage = job.ErrorMessage,
            CreatedAt = job.CreatedAt,
            StartedAt = job.StartedAt,
            CompletedAt = job.CompletedAt,
            DurationSeconds = job.DurationSeconds,
            TrainedModelId = job.TrainedModelId
        };
    }
}

// DTOs

public record CreateDatasetRequest(string Name, string? Description);

public record UpdateDatasetRequest(
    string? Name,
    string? Description,
    TrainingDatasetStatus? Status);

public record AddStemRequest(
    Guid StemId,
    float? Weight,
    string? Notes);

public record UpdateStemRequest(
    float? Weight,
    string? Notes);

public record StartTrainingRequest(
    Guid DatasetId,
    string ModelName,
    int? Epochs = 100,
    float? LearningRate = 1e-4f,
    int? LoraRank = 8,
    int? LoraAlpha = 16,
    int? BatchSize = 1);

// Training Job DTOs

public record CreateTrainingJobRequest(
    Guid DatasetId,
    string ModelName,
    string? BaseModel = null,
    int? Epochs = null,
    float? LearningRate = null,
    int? LoraRank = null,
    int? LoraAlpha = null,
    int? BatchSize = null
);

public record TrainingCallbackRequest(
    string JobId,
    string Status,
    string? ModelId = null,
    string? ModelPath = null,
    float? TrainingTime = null,
    float? FinalLoss = null,
    string? ErrorMessage = null
);

public record TrainingJobDto
{
    public Guid Id { get; init; }
    public Guid DatasetId { get; init; }
    public string? DatasetName { get; init; }
    public string ModelName { get; init; } = string.Empty;
    public string BaseModel { get; init; } = string.Empty;
    public string Status { get; init; } = string.Empty;
    public float Progress { get; init; }
    public int CurrentEpoch { get; init; }
    public int TotalEpochs { get; init; }
    public float? CurrentLoss { get; init; }
    public string? ErrorMessage { get; init; }
    public DateTime CreatedAt { get; init; }
    public DateTime? StartedAt { get; init; }
    public DateTime? CompletedAt { get; init; }
    public float? DurationSeconds { get; init; }
    public Guid? TrainedModelId { get; init; }
}

