using Microsoft.EntityFrameworkCore;
using Azure.Storage.Blobs;
using Azure.Identity;
using Azure.Messaging.ServiceBus;
using MusicPlatform.Api.Services;
using MusicPlatform.Api.Hubs;

var builder = WebApplication.CreateBuilder(args);

// ======================================
// Configuration-Driven Service Registration
// ======================================

// 1. Database Context (PostgreSQL for local, SQL Server for Azure)
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
if (connectionString != null && connectionString.Contains("Host="))
{
    // PostgreSQL (Local)
    builder.Services.AddDbContext<MusicPlatform.Infrastructure.Data.MusicPlatformDbContext>(options =>
        options.UseNpgsql(connectionString, b => b.MigrationsAssembly("MusicPlatform.Api")));
}
else
{
    // SQL Server (Azure)
    builder.Services.AddDbContext<MusicPlatform.Infrastructure.Data.MusicPlatformDbContext>(options =>
        options.UseSqlServer(connectionString ?? string.Empty, b => b.MigrationsAssembly("MusicPlatform.Api")));
}

// 2. Blob Storage Service
var useManagedIdentity = builder.Configuration.GetValue<bool>("BlobStorage:UseManagedIdentity");
if (useManagedIdentity)
{
    // Azure: Managed Identity
    var accountName = builder.Configuration["BlobStorage:AccountName"];
    var blobServiceUri = new Uri($"https://{accountName}.blob.core.windows.net");
    builder.Services.AddSingleton(new BlobServiceClient(blobServiceUri, new DefaultAzureCredential()));
}
else
{
    // Local: Azurite connection string
    var blobConnectionString = builder.Configuration["BlobStorage:ConnectionString"];
    builder.Services.AddSingleton(new BlobServiceClient(blobConnectionString));
}

// 2.1 Service Bus (for training job queue)
var serviceBusNamespace = builder.Configuration["ServiceBus:Namespace"];
if (!string.IsNullOrEmpty(serviceBusNamespace))
{
    if (useManagedIdentity)
    {
        // Azure: Managed Identity
        builder.Services.AddSingleton(new ServiceBusClient(
            $"{serviceBusNamespace}.servicebus.windows.net",
            new DefaultAzureCredential()));
    }
    else
    {
        // Local: Connection string (if provided)
        var serviceBusConnectionString = builder.Configuration["ServiceBus:ConnectionString"];
        if (!string.IsNullOrEmpty(serviceBusConnectionString))
        {
            builder.Services.AddSingleton(new ServiceBusClient(serviceBusConnectionString));
        }
    }
}

// 3. Worker Client Configuration
builder.Services.AddHttpClient("AnalysisWorker", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["Workers:AnalysisWorkerUrl"]);
    client.Timeout = TimeSpan.FromMinutes(15); // Increased for Demucs separation + MIR analysis
});
builder.Services.AddHttpClient("GenerationWorker", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["Workers:GenerationWorkerUrl"]);
    client.Timeout = TimeSpan.FromMinutes(15); // Increased for generation processing
});

// 4. Orchestration Service (In-Memory for local, Durable Functions for Azure)
var orchestrationType = builder.Configuration["Orchestration:Type"];
builder.Services.AddHostedService<JobOrchestrationService>();

// 4.1. Worker Autoscaler (for Docker Compose environments)
builder.Services.AddHostedService<WorkerAutoscalerService>();

// 5. Application Services
builder.Services.AddScoped<IdempotentJobService>();

// 5.1. SignalR for real-time progress updates
builder.Services.AddSignalR();
builder.Services.AddScoped<JobProgressService>();

// 6. Controllers and OpenAPI
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        // Serialize enums as strings instead of numbers
        options.JsonSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter());
    });

// Configure file upload size limits (up to 100MB for audio files)
builder.Services.Configure<Microsoft.AspNetCore.Http.Features.FormOptions>(options =>
{
    options.MultipartBodyLengthLimit = 104_857_600; // 100 MB
    options.ValueLengthLimit = 104_857_600;
    options.MultipartHeadersLengthLimit = 104_857_600;
});

builder.Services.Configure<Microsoft.AspNetCore.Server.Kestrel.Core.KestrelServerOptions>(options =>
{
    options.Limits.MaxRequestBodySize = 104_857_600; // 100 MB
});

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// 6. CORS (for MAUI app + SignalR)
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        // MAUI apps are native and don't send Origin headers, so we need to allow all origins
        // This is safe for MAUI because authentication/authorization should be handled separately
        policy.SetIsOriginAllowed(_ => true) // Allow any origin (required for MAUI)
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials(); // Required for SignalR
    });
});

// Build the app
var app = builder.Build();

// ======================================
// Middleware Pipeline
// ======================================

// Swagger (always enabled for now - can be restricted later)
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseCors();
app.UseAuthorization();
app.MapControllers();

// Map SignalR hub
app.MapHub<JobProgressHub>("/hubs/jobprogress");

// Health Check Endpoint
app.MapGet("/health", () => Results.Ok(new 
{ 
    status = "healthy", 
    environment = builder.Configuration["Environment"],
    timestamp = DateTime.UtcNow 
}));

app.Run();
