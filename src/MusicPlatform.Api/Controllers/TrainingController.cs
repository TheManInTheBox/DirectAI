using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Entities;
using MusicPlatform.Infrastructure.Data;
using System.Text.Json;

namespace MusicPlatform.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class TrainingController : ControllerBase
{
    private readonly MusicPlatformDbContext _context;
    private readonly ILogger<TrainingController> _logger;

    public TrainingController(
        MusicPlatformDbContext context,
        ILogger<TrainingController> logger)
    {
        _context = context;
        _logger = logger;
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
