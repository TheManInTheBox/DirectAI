using Microsoft.EntityFrameworkCore;
using Azure.Storage.Blobs;
using Azure.Identity;
using MusicPlatform.Api.Services;

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

// 5. Application Services
builder.Services.AddScoped<IdempotentJobService>();

// 6. Controllers and OpenAPI
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        // Serialize enums as strings instead of numbers
        options.JsonSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter());
    });
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// 6. CORS (for local MAUI app development)
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        if (builder.Environment.IsDevelopment())
        {
            policy.AllowAnyOrigin()
                  .AllowAnyMethod()
                  .AllowAnyHeader();
        }
        else
        {
            // Production: Only allow MAUI app origins
            policy.WithOrigins("https://music-app.azurewebsites.net")
                  .AllowAnyMethod()
                  .AllowAnyHeader();
        }
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

// Health Check Endpoint
app.MapGet("/health", () => Results.Ok(new 
{ 
    status = "healthy", 
    environment = builder.Configuration["Environment"],
    timestamp = DateTime.UtcNow 
}));

app.Run();
