using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using Microsoft.AspNetCore.SignalR.Client;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// ViewModel for the Jobs page - displays background processing queue
/// </summary>
public class JobsViewModel : INotifyPropertyChanged, IDisposable
{
    private readonly MusicPlatformApiClient _apiClient;
    private readonly ApiSettings _apiSettings;
    private HubConnection? _hubConnection;
    private string _statusMessage = string.Empty;
    private bool _isRefreshing = false;
    private JobStatisticsDto _statistics = new(0, 0, 0, 0, 0, 0, 0, 0, 0);
    private CancellationTokenSource? _autoRefreshCts;
    private bool _isRealTimeMode = true;
    private bool _isSignalRConnected = false;

    public ObservableCollection<JobItem> Jobs { get; } = new();

    public string StatusMessage
    {
        get => _statusMessage;
        set
        {
            _statusMessage = value;
            OnPropertyChanged();
        }
    }

    public bool IsRefreshing
    {
        get => _isRefreshing;
        set
        {
            _isRefreshing = value;
            OnPropertyChanged();
        }
    }

    public JobStatisticsDto Statistics
    {
        get => _statistics;
        set
        {
            _statistics = value;
            OnPropertyChanged();
        }
    }

    public ICommand RefreshCommand { get; }
    public ICommand CancelJobCommand { get; }
    public ICommand RetryJobCommand { get; }

    public JobsViewModel(MusicPlatformApiClient apiClient, ApiSettings apiSettings)
    {
        _apiClient = apiClient;
        _apiSettings = apiSettings;
        
        // Initialize Statistics with default values to prevent null reference
        Statistics = new JobStatisticsDto(
            TotalJobs: 0,
            PendingJobs: 0,
            RunningJobs: 0,
            CompletedJobs: 0,
            FailedJobs: 0,
            CancelledJobs: 0,
            AnalysisJobs: 0,
            GenerationJobs: 0,
            AverageCompletionTimeSeconds: 0
        );
        
        RefreshCommand = new Command(async () => await LoadJobsAsync());
        CancelJobCommand = new Command<JobItem>(async (job) => await CancelJobAsync(job));
        RetryJobCommand = new Command<JobItem>(async (job) => await RetryJobAsync(job));

        // Initialize SignalR connection
        InitializeSignalRConnection();

        // Load jobs on initialization
        Task.Run(async () => await LoadJobsAsync());

        // Start real-time auto-refresh with adaptive polling (fallback when SignalR isn't connected)
        StartRealTimeRefresh();
    }

    private void InitializeSignalRConnection()
    {
        try
        {
            // Get the API base URL from the API settings
            var apiBaseUrl = _apiSettings.BaseUrl.TrimEnd('/');
            
            _hubConnection = new HubConnectionBuilder()
                .WithUrl($"{apiBaseUrl}/hubs/jobprogress")
                .WithAutomaticReconnect()
                .Build();

            // Set up event handlers for job progress updates
            _hubConnection.On<Guid, string, string>("JobStatusUpdated", async (jobId, status, message) =>
            {
                await MainThread.InvokeOnMainThreadAsync(() =>
                {
                    var job = Jobs.FirstOrDefault(j => j.Id == jobId);
                    if (job != null)
                    {
                        job.Status = status;
                        StatusMessage = $"📡 Real-time update: {message}";
                    }
                });
            });

            _hubConnection.On<Guid, string, string, int, string>("JobProgressUpdated", async (jobId, status, currentStep, progressPercentage, message) =>
            {
                await MainThread.InvokeOnMainThreadAsync(() =>
                {
                    var job = Jobs.FirstOrDefault(j => j.Id == jobId);
                    if (job != null)
                    {
                        job.Status = status;
                        job.CurrentStep = currentStep;
                        job.ProgressPercentage = progressPercentage;
                        StatusMessage = $"📡 Real-time: {message} ({progressPercentage}%)";
                    }
                });
            });

            _hubConnection.On<Guid, bool, object>("AnalysisCompleted", async (jobId, success, analysisResult) =>
            {
                await MainThread.InvokeOnMainThreadAsync(() =>
                {
                    var job = Jobs.FirstOrDefault(j => j.Id == jobId);
                    if (job != null)
                    {
                        job.Status = success ? "Completed" : "Failed";
                        job.ProgressPercentage = 100;
                        StatusMessage = success 
                            ? "📡 ✅ Analysis completed successfully!" 
                            : "📡 ❌ Analysis failed";
                        
                        // Trigger a data refresh to get updated completion details
                        Task.Run(async () => await LoadJobsAsync());
                    }
                });
            });

            // Handle connection state changes
            _hubConnection.Closed += async (error) =>
            {
                _isSignalRConnected = false;
                await MainThread.InvokeOnMainThreadAsync(() =>
                {
                    StatusMessage = "📡 SignalR disconnected, using polling...";
                });
            };

            _hubConnection.Reconnected += async (connectionId) =>
            {
                _isSignalRConnected = true;
                await MainThread.InvokeOnMainThreadAsync(() =>
                {
                    StatusMessage = "📡 SignalR reconnected for real-time updates!";
                });
            };

            // Start the connection
            Task.Run(async () => await StartSignalRConnection());
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"SignalR initialization error: {ex.Message}");
            StatusMessage = "📡 SignalR setup failed, using polling mode";
        }
    }

    private async Task StartSignalRConnection()
    {
        try
        {
            if (_hubConnection != null)
            {
                await _hubConnection.StartAsync();
                _isSignalRConnected = true;
                
                await MainThread.InvokeOnMainThreadAsync(() =>
                {
                    StatusMessage = "📡 Connected to real-time job updates!";
                });
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"SignalR connection error: {ex.Message}");
            _isSignalRConnected = false;
            
            await MainThread.InvokeOnMainThreadAsync(() =>
            {
                StatusMessage = "📡 Real-time connection failed, using polling mode";
            });
        }
    }

    private async Task StopSignalRConnection()
    {
        try
        {
            if (_hubConnection != null)
            {
                await _hubConnection.StopAsync();
                await _hubConnection.DisposeAsync();
                _hubConnection = null;
                _isSignalRConnected = false;
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"SignalR disconnect error: {ex.Message}");
        }
    }

    private async Task LoadJobsAsync()
    {
        try
        {
            IsRefreshing = true;
            
            // Load jobs
            var jobs = await _apiClient.GetAllJobsAsync(take: 50);
            
            // Load statistics
            var stats = await _apiClient.GetJobStatisticsAsync();

            await MainThread.InvokeOnMainThreadAsync(() =>
            {
                // Smart update: Only clear and rebuild if count changed significantly
                // Otherwise, update existing items to prevent UI flickering
                if (jobs == null || jobs.Count() == 0)
                {
                    Jobs.Clear();
                }
                else if (Math.Abs(Jobs.Count - jobs.Count()) > 3)
                {
                    // Significant change - rebuild list
                    Jobs.Clear();
                    foreach (var job in jobs)
                    {
                        Jobs.Add(CreateJobItem(job));
                    }
                }
                else
                {
                    // Update existing items and add new ones
                    var jobDict = jobs.ToDictionary(j => j.Id);
                    
                    // Remove jobs that no longer exist
                    for (int i = Jobs.Count - 1; i >= 0; i--)
                    {
                        if (!jobDict.ContainsKey(Jobs[i].Id))
                        {
                            Jobs.RemoveAt(i);
                        }
                    }
                    
                    // Update existing jobs and add new ones
                    foreach (var job in jobs)
                    {
                        var existing = Jobs.FirstOrDefault(j => j.Id == job.Id);
                        if (existing != null)
                        {
                            UpdateJobItem(existing, job);
                        }
                        else
                        {
                            Jobs.Add(CreateJobItem(job));
                        }
                    }
                }

                Statistics = stats ?? new JobStatisticsDto(
                    TotalJobs: 0,
                    PendingJobs: 0,
                    RunningJobs: 0,
                    CompletedJobs: 0,
                    FailedJobs: 0,
                    CancelledJobs: 0,
                    AnalysisJobs: 0,
                    GenerationJobs: 0,
                    AverageCompletionTimeSeconds: 0
                );
                
                // Update status message with real-time indicator
                var activeJobs = Jobs.Count(j => j.Status == "Running" || j.Status == "Pending");
                StatusMessage = activeJobs > 0 
                    ? $"🔄 Live: {activeJobs} active job(s) • Refreshing every {GetRefreshInterval()}s"
                    : $"✅ {Jobs.Count} job(s) • All idle";
            });
        }
        catch (Exception ex)
        {
            await MainThread.InvokeOnMainThreadAsync(() =>
            {
                StatusMessage = $"❌ Error loading jobs: {ex.Message}";
                System.Diagnostics.Debug.WriteLine($"JobsViewModel Error: {ex}");
            });
        }
        finally
        {
            IsRefreshing = false;
        }
    }

    private JobItem CreateJobItem(JobDto job)
    {
        var jobItem = new JobItem
        {
            Id = job.Id,
            Type = job.Type,
            EntityId = job.EntityId,
            Status = job.Status,
            StatusIcon = GetStatusIcon(job.Status),
            StatusColor = GetStatusColor(job.Status),
            StartedAt = job.StartedAt.ToLocalTime(),
            CompletedAt = job.CompletedAt?.ToLocalTime(),
            LastHeartbeat = job.LastHeartbeat?.ToLocalTime(),
            ErrorMessage = job.ErrorMessage,
            Duration = job.CompletedAt.HasValue 
                ? FormatDuration(job.CompletedAt.Value - job.StartedAt)
                : FormatRunningDuration(job.StartedAt),
            CanCancel = job.Status == "Pending" || job.Status == "Running",
            CanRetry = job.Status == "Failed" && job.RetryCount < job.MaxRetries,
            
            // Idempotent features
            IdempotencyKey = job.IdempotencyKey,
            RetryCount = job.RetryCount,
            MaxRetries = job.MaxRetries,
            WorkerInstanceId = job.WorkerInstanceId,
            CurrentStep = job.CurrentStep,
            Checkpoints = job.Checkpoints
        };

        // Set progress message and percentage
        jobItem.ProgressMessage = GetProgressMessage(job.Status, job.CurrentStep, jobItem.IsStale);
        jobItem.ProgressPercentage = GetProgressPercentage(job.Status, job.CurrentStep);

        return jobItem;
    }

    private void UpdateJobItem(JobItem existing, JobDto job)
    {
        existing.Status = job.Status;
        existing.StatusIcon = GetStatusIcon(job.Status);
        existing.StatusColor = GetStatusColor(job.Status);
        existing.CompletedAt = job.CompletedAt?.ToLocalTime();
        existing.LastHeartbeat = job.LastHeartbeat?.ToLocalTime();
        existing.ErrorMessage = job.ErrorMessage;
        existing.Duration = job.CompletedAt.HasValue 
            ? FormatDuration(job.CompletedAt.Value - job.StartedAt)
            : FormatRunningDuration(job.StartedAt);
        existing.CanCancel = job.Status == "Pending" || job.Status == "Running";
        existing.CanRetry = job.Status == "Failed" && job.RetryCount < job.MaxRetries;
        existing.WorkerInstanceId = job.WorkerInstanceId;
        existing.CurrentStep = job.CurrentStep;
        existing.Checkpoints = job.Checkpoints;
        
        // Update progress
        existing.ProgressMessage = GetProgressMessage(job.Status, job.CurrentStep, existing.IsStale);
        existing.ProgressPercentage = GetProgressPercentage(job.Status, job.CurrentStep);
    }

    private int GetRefreshInterval()
    {
        // When SignalR is connected, poll much less frequently since we get real-time updates
        if (_isSignalRConnected)
        {
            return 30; // Poll every 30 seconds just for statistics and new jobs
        }
        
        // Fallback to aggressive polling when SignalR is not connected
        var activeJobs = Jobs.Count(j => j.Status == "Running" || j.Status == "Pending");
        return activeJobs > 0 ? 2 : 5; // 2s when active, 5s when idle
    }

    private async Task CancelJobAsync(JobItem job)
    {
        if (job == null) return;

        try
        {
            StatusMessage = $"🛑 Cancelling job {job.Id}...";
            await _apiClient.CancelJobAsync(job.Id);
            await LoadJobsAsync();
            StatusMessage = $"✅ Job cancelled";
        }
        catch (Exception ex)
        {
            StatusMessage = $"❌ Error cancelling job: {ex.Message}";
        }
    }

    private async Task RetryJobAsync(JobItem job)
    {
        if (job == null) return;

        try
        {
            StatusMessage = $"🔄 Retrying job {job.Id}...";
            await _apiClient.RetryJobAsync(job.Id);
            await LoadJobsAsync();
            StatusMessage = $"✅ Job retry submitted";
        }
        catch (Exception ex)
        {
            StatusMessage = $"❌ Error retrying job: {ex.Message}";
        }
    }

    private void StartRealTimeRefresh()
    {
        _autoRefreshCts = new CancellationTokenSource();
        
        Task.Run(async () =>
        {
            while (!_autoRefreshCts.Token.IsCancellationRequested)
            {
                try
                {
                    // Adaptive polling: much slower when SignalR is connected, faster when jobs are active
                    var interval = GetRefreshInterval() * 1000; // Convert to milliseconds
                    await Task.Delay(interval, _autoRefreshCts.Token);
                    
                    if (_isRealTimeMode && !IsRefreshing)
                    {
                        await LoadJobsAsync();
                    }
                }
                catch (TaskCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"Auto-refresh error: {ex.Message}");
                    await Task.Delay(5000, _autoRefreshCts.Token); // Back off on error
                }
            }
        }, _autoRefreshCts.Token);
    }

    public void StopRealTimeRefresh()
    {
        _autoRefreshCts?.Cancel();
        _isRealTimeMode = false;
    }

    public void StartRealTimeMode()
    {
        if (!_isRealTimeMode)
        {
            _isRealTimeMode = true;
            StartRealTimeRefresh();
        }
    }

    private static string GetStatusIcon(string status)
    {
        return status switch
        {
            "Pending" => "⏸️",
            "Running" => "⚙️",
            "Completed" => "✅",
            "Failed" => "❌",
            "Cancelled" => "🛑",
            "Stale" => "💤",
            "Retrying" => "🔄",
            "Suspended" => "⏯️",
            _ => "❓"
        };
    }

    private static Color GetStatusColor(string status)
    {
        return status switch
        {
            "Pending" => Colors.Orange,
            "Running" => Colors.Blue,
            "Completed" => Colors.Green,
            "Failed" => Colors.Red,
            "Cancelled" => Colors.Gray,
            "Stale" => Colors.Purple,
            "Retrying" => Colors.Orange,
            "Suspended" => Colors.Brown,
            _ => Colors.Black
        };
    }

    private static string FormatDuration(TimeSpan duration)
    {
        if (duration.TotalSeconds < 60)
            return $"{duration.TotalSeconds:F1}s";
        else if (duration.TotalMinutes < 60)
            return $"{duration.TotalMinutes:F1}m";
        else
            return $"{duration.TotalHours:F1}h";
    }

    private static string FormatRunningDuration(DateTime startedAt)
    {
        var running = DateTime.UtcNow - startedAt.ToUniversalTime();
        return $"Running {FormatDuration(running)}";
    }

    private static string GetProgressMessage(string status, string? currentStep, bool isStale)
    {
        if (isStale)
            return "⚠️ Worker appears to be unresponsive";

        if (status == "Running" && !string.IsNullOrEmpty(currentStep))
        {
            return currentStep switch
            {
                "initializing" => "🚀 Starting comprehensive analysis...",
                "downloading_audio" => "⬇️ Downloading MP3 file from storage...",
                "calling_analysis_worker" => "📞 Calling enhanced analysis worker...",
                "worker_processing" => "🔬 AI Analysis Pipeline: Source separation + MIR + Audio Flamingo + Bark training data...",
                "source_separation" => "🎵 Separating audio into stems (vocals, drums, bass, other)...",
                "mir_analysis" => "🎼 Extracting music features (BPM, key, chords, beats, sections)...",
                "flamingo_analysis" => "🦩 Audio Flamingo: Analyzing genre, mood, instruments...",
                "stem_analysis" => "🔍 Individual stem analysis with instrument-specific features...",
                "bark_preparation" => "🎯 Preparing Bark training dataset with structured prompts...",
                "uploading_results" => "⬆️ Uploading stems, analysis results, and training data...",
                "database_storage" => "💾 Storing comprehensive analysis results in database...",
                _ => $"🔄 {currentStep.Replace('_', ' ')}"
            };
        }

        return status switch
        {
            "Pending" => "⏸️ Waiting to start...",
            "Running" => "⚙️ Processing...",
            "Completed" => "✅ Analysis complete",
            "Failed" => "❌ Analysis failed",
            "Cancelled" => "🛑 Cancelled by user",
            "Stale" => "💤 Worker became unresponsive",
            "Retrying" => "🔄 Preparing to retry...",
            "Suspended" => "⏯️ Temporarily suspended",
            _ => ""
        };
    }

    private static int GetProgressPercentage(string status, string? currentStep)
    {
        if (status == "Completed")
            return 100;
        
        if (status == "Failed" || status == "Cancelled")
            return 0;
        
        if (status == "Pending")
            return 0;

        if (status == "Running" && !string.IsNullOrEmpty(currentStep))
        {
            return currentStep switch
            {
                "initializing" => 5,
                "downloading_audio" => 10,
                "calling_analysis_worker" => 15,
                "worker_processing" => 40, // General processing - covers multiple sub-steps
                "source_separation" => 25,
                "mir_analysis" => 35,
                "flamingo_analysis" => 50,
                "stem_analysis" => 65,
                "bark_preparation" => 75,
                "uploading_results" => 85,
                "database_storage" => 95,
                _ => 50
            };
        }

        return 25; // Default for running without specific step
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    protected virtual void Dispose(bool disposing)
    {
        if (disposing)
        {
            StopRealTimeRefresh();
            Task.Run(async () => await StopSignalRConnection());
        }
    }
}

/// <summary>
/// UI model for a job with enhanced status tracking
/// </summary>
public class JobItem : INotifyPropertyChanged
{
    private string _statusMessage = string.Empty;
    private string _progressMessage = string.Empty;
    private int _progressPercentage = 0;

    public Guid Id { get; set; }
    public string Type { get; set; } = string.Empty;
    public Guid EntityId { get; set; }
    public string Status { get; set; } = string.Empty;
    public string StatusIcon { get; set; } = string.Empty;
    public Color StatusColor { get; set; } = Colors.Black;
    public DateTime StartedAt { get; set; }
    public DateTime? CompletedAt { get; set; }
    public DateTime? LastHeartbeat { get; set; }
    public string? ErrorMessage { get; set; }
    public string Duration { get; set; } = string.Empty;
    public bool CanCancel { get; set; }
    public bool CanRetry { get; set; }

    // New idempotent features
    public string? IdempotencyKey { get; set; }
    public int RetryCount { get; set; }
    public int MaxRetries { get; set; }
    public string? WorkerInstanceId { get; set; }
    public string? CurrentStep { get; set; }
    public Dictionary<string, object>? Checkpoints { get; set; }

    // Computed properties
    public string RetryInfo => RetryCount > 0 ? $"Retry {RetryCount}/{MaxRetries}" : "";
    public bool HasRetries => RetryCount > 0;
    public bool IsStale => Status == "Running" && LastHeartbeat.HasValue && 
                          (DateTime.UtcNow - LastHeartbeat.Value).TotalMinutes > 5;
    public string HeartbeatStatus => LastHeartbeat?.ToString("HH:mm:ss") ?? "No heartbeat";
    public string WorkerInfo => string.IsNullOrEmpty(WorkerInstanceId) ? "No worker" : $"Worker: {WorkerInstanceId}";

    public string StatusMessage
    {
        get => _statusMessage;
        set
        {
            _statusMessage = value;
            OnPropertyChanged();
        }
    }

    public string ProgressMessage
    {
        get => _progressMessage;
        set
        {
            _progressMessage = value;
            OnPropertyChanged();
        }
    }

    public int ProgressPercentage
    {
        get => _progressPercentage;
        set
        {
            _progressPercentage = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(ProgressDecimal));
        }
    }

    public double ProgressDecimal => _progressPercentage / 100.0;

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
