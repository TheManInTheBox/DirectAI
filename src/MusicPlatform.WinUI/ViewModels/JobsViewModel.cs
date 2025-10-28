using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MusicPlatform.WinUI.Models;
using MusicPlatform.WinUI.Services;
using System.Collections.ObjectModel;
using Windows.System;

namespace MusicPlatform.WinUI.ViewModels;

public partial class JobsViewModel : ObservableObject, IDisposable
{
    private readonly MusicPlatformApiClient _apiClient;
    private readonly SignalRService _signalRService;
    private readonly DispatcherTimer _refreshTimer;

    [ObservableProperty]
    private ObservableCollection<JobDto> _jobs = new();

    [ObservableProperty]
    private bool _isLoading;

    public int RunningJobsCount => Jobs.Count(j => j.Status.Equals("Running", StringComparison.OrdinalIgnoreCase) || 
                                                     j.Status.Equals("Pending", StringComparison.OrdinalIgnoreCase));
    
    public int CompletedJobsCount => Jobs.Count(j => j.Status.Equals("Completed", StringComparison.OrdinalIgnoreCase));
    
    public int FailedJobsCount => Jobs.Count(j => j.Status.Equals("Failed", StringComparison.OrdinalIgnoreCase));

    public JobsViewModel(MusicPlatformApiClient apiClient, SignalRService signalRService)
    {
        _apiClient = apiClient;
        _signalRService = signalRService;
        _signalRService.JobUpdated += OnJobUpdated;
        
        // Set up periodic refresh timer (every 30 seconds)
        _refreshTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(30)
        };
        _refreshTimer.Tick += (s, e) => _ = LoadJobsAsync();
    }

    public void StartPeriodicRefresh()
    {
        _refreshTimer.Start();
    }

    public void StopPeriodicRefresh()
    {
        _refreshTimer.Stop();
    }

    [RelayCommand]
    private async Task LoadJobsAsync()
    {
        await LoadJobsInternalAsync();
    }

    public async Task LoadJobsInternalAsync()
    {
        IsLoading = true;
        try
        {
            var jobs = await _apiClient.GetAllJobsAsync();
            Jobs.Clear();
            if (jobs != null)
            {
                foreach (var job in jobs.OrderByDescending(j => j.StartedAt))
                {
                    Jobs.Add(job);
                }
            }
            
            // Notify computed properties
            OnPropertyChanged(nameof(RunningJobsCount));
            OnPropertyChanged(nameof(CompletedJobsCount));
            OnPropertyChanged(nameof(FailedJobsCount));
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error loading jobs: {ex.Message}");
        }
        finally
        {
            IsLoading = false;
        }
    }

    private void OnJobUpdated(object? sender, JobUpdateEventArgs e)
    {
        // Find and update the specific job in the collection
        var existingJob = Jobs.FirstOrDefault(j => j.Id == e.JobId);
        if (existingJob != null)
        {
            // Update the existing job with new status
            var updatedJob = existingJob with
            {
                Status = e.Status,
                LastHeartbeat = DateTime.UtcNow,
                CurrentStep = e.Message ?? existingJob.CurrentStep,
                CompletedAt = e.Status.Equals("Completed", StringComparison.OrdinalIgnoreCase) || 
                             e.Status.Equals("Failed", StringComparison.OrdinalIgnoreCase) ? 
                             DateTime.UtcNow : existingJob.CompletedAt,
                ErrorMessage = e.Status.Equals("Failed", StringComparison.OrdinalIgnoreCase) ? 
                              e.Message : existingJob.ErrorMessage
            };

            // Replace the job in the collection
            var index = Jobs.IndexOf(existingJob);
            Jobs[index] = updatedJob;
            
            // Notify computed properties
            OnPropertyChanged(nameof(RunningJobsCount));
            OnPropertyChanged(nameof(CompletedJobsCount));
            OnPropertyChanged(nameof(FailedJobsCount));
        }
        else
        {
            // Job not found in current list, reload to get new jobs
            _ = LoadJobsAsync();
        }
    }

    public void Dispose()
    {
        _refreshTimer?.Stop();
        _signalRService.JobUpdated -= OnJobUpdated;
    }
}
