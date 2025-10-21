using Microsoft.AspNetCore.SignalR;

namespace MusicPlatform.Api.Hubs;

/// <summary>
/// SignalR hub for real-time job progress updates
/// </summary>
public class JobProgressHub : Hub
{
    /// <summary>
    /// Called when client connects to the hub
    /// </summary>
    public async Task JoinGroup(string groupName)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, groupName);
    }

    /// <summary>
    /// Called when client leaves a group
    /// </summary>
    public async Task LeaveGroup(string groupName)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, groupName);
    }

    /// <summary>
    /// Called when client disconnects
    /// </summary>
    public override async Task OnDisconnectedAsync(Exception? exception)
    {
        await base.OnDisconnectedAsync(exception);
    }
}

/// <summary>
/// Service for sending job progress updates via SignalR
/// </summary>
public class JobProgressService
{
    private readonly IHubContext<JobProgressHub> _hubContext;
    private readonly ILogger<JobProgressService> _logger;

    public JobProgressService(IHubContext<JobProgressHub> hubContext, ILogger<JobProgressService> logger)
    {
        _hubContext = hubContext;
        _logger = logger;
    }

    /// <summary>
    /// Send job status update to all connected clients
    /// </summary>
    public async Task SendJobStatusUpdate(Guid jobId, string status, string? currentStep = null, int? progressPercentage = null)
    {
        try
        {
            var update = new
            {
                JobId = jobId,
                Status = status,
                CurrentStep = currentStep,
                ProgressPercentage = progressPercentage,
                Timestamp = DateTime.UtcNow
            };

            // Send to all clients in the "jobs" group
            await _hubContext.Clients.Group("jobs").SendAsync("JobStatusUpdated", update);
            
            // Also send to specific job group for targeted updates
            await _hubContext.Clients.Group($"job-{jobId}").SendAsync("JobStatusUpdated", update);
            
            _logger.LogInformation("Job status update sent: JobId={JobId}, Status={Status}, Step={CurrentStep}, Progress={Progress}%", 
                jobId, status, currentStep, progressPercentage);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending job status update for JobId={JobId}", jobId);
        }
    }

    /// <summary>
    /// Send comprehensive job progress update with detailed information
    /// </summary>
    public async Task SendJobProgressUpdate(Guid jobId, string status, string? currentStep = null, 
        int? progressPercentage = null, string? progressMessage = null, Dictionary<string, object>? metadata = null)
    {
        try
        {
            var update = new
            {
                JobId = jobId,
                Status = status,
                CurrentStep = currentStep,
                ProgressPercentage = progressPercentage,
                ProgressMessage = progressMessage,
                Metadata = metadata ?? new Dictionary<string, object>(),
                Timestamp = DateTime.UtcNow
            };

            await _hubContext.Clients.Group("jobs").SendAsync("JobProgressUpdated", update);
            await _hubContext.Clients.Group($"job-{jobId}").SendAsync("JobProgressUpdated", update);
            
            _logger.LogDebug("Job progress update sent: JobId={JobId}, Message={Message}", jobId, progressMessage);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending job progress update for JobId={JobId}", jobId);
        }
    }

    /// <summary>
    /// Send analysis completion notification with comprehensive results
    /// </summary>
    public async Task SendAnalysisCompletionUpdate(Guid jobId, object analysisResults)
    {
        try
        {
            var update = new
            {
                JobId = jobId,
                Status = "Completed",
                ProgressPercentage = 100,
                ProgressMessage = "🎉 Comprehensive analysis complete with Bark training data!",
                AnalysisResults = analysisResults,
                Timestamp = DateTime.UtcNow
            };

            await _hubContext.Clients.Group("jobs").SendAsync("AnalysisCompleted", update);
            await _hubContext.Clients.Group($"job-{jobId}").SendAsync("AnalysisCompleted", update);
            
            _logger.LogInformation("Analysis completion update sent: JobId={JobId}", jobId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending analysis completion update for JobId={JobId}", jobId);
        }
    }
}