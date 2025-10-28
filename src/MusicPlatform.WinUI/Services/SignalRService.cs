using Microsoft.AspNetCore.SignalR.Client;

namespace MusicPlatform.WinUI.Services;

public class SignalRService : IAsyncDisposable
{
    private HubConnection? _connection;
    private readonly string _hubUrl;

    public event EventHandler<JobUpdateEventArgs>? JobUpdated;
    public bool IsConnected => _connection?.State == HubConnectionState.Connected;

    public SignalRService(string baseUrl)
    {
        _hubUrl = $"{baseUrl}/hubs/jobs";
    }

    public async Task StartAsync()
    {
        if (_connection != null)
            return;

        _connection = new HubConnectionBuilder()
            .WithUrl(_hubUrl)
            .WithAutomaticReconnect()
            .Build();

        _connection.On<Guid, string, int, string?>("ReceiveJobUpdate", (jobId, status, progress, message) =>
        {
            JobUpdated?.Invoke(this, new JobUpdateEventArgs(jobId, status, progress, message));
        });

        await _connection.StartAsync();
    }

    // no-op restart in static config scenario (stop+start helper retained if needed later)

    public async Task StopAsync()
    {
        if (_connection != null)
        {
            await _connection.StopAsync();
            await _connection.DisposeAsync();
            _connection = null;
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync();
    }
}

public class JobUpdateEventArgs : EventArgs
{
    public Guid JobId { get; }
    public string Status { get; }
    public int Progress { get; }
    public string? Message { get; }

    public JobUpdateEventArgs(Guid jobId, string status, int progress, string? message)
    {
        JobId = jobId;
        Status = status;
        Progress = progress;
        Message = message;
    }
}
