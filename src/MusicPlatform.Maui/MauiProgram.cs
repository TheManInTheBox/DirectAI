using Microsoft.Extensions.Logging;
using MusicPlatform.Maui.Services;
using MusicPlatform.Maui.Pages;
using MusicPlatform.Maui.ViewModels;
using MusicPlatform.Maui.Converters;
using CommunityToolkit.Maui;

namespace MusicPlatform.Maui;

public static class MauiProgram
{
	public static MauiApp CreateMauiApp()
	{
		var builder = MauiApp.CreateBuilder();
		builder
			.UseMauiApp<App>()
			.UseMauiCommunityToolkit()
			.UseMauiCommunityToolkitMediaElement()
			.ConfigureFonts(fonts =>
			{
				fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
				fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold");
			});

#if DEBUG
		builder.Logging.AddDebug();
#endif

		// Register API settings
		var apiSettings = new ApiSettings();
		builder.Services.AddSingleton(apiSettings);

		// Register HTTP client for API communication
		builder.Services.AddHttpClient<MusicPlatformApiClient>(client =>
		{
			client.BaseAddress = new Uri(apiSettings.BaseUrl);
			client.Timeout = TimeSpan.FromSeconds(apiSettings.TimeoutSeconds);
		})
		.ConfigurePrimaryHttpMessageHandler(() =>
		{
			var handler = new HttpClientHandler();
#if DEBUG
			// For development only - bypass SSL certificate validation
			handler.ServerCertificateCustomValidationCallback = 
				HttpClientHandler.DangerousAcceptAnyServerCertificateValidator;
#endif
			return handler;
		});

		// Register HTTP client for image downloading
		builder.Services.AddHttpClient<ImageCacheService>(client =>
		{
			client.Timeout = TimeSpan.FromSeconds(30);
		});

		// Register ViewModels
		builder.Services.AddTransient<MainViewModel>();
		builder.Services.AddTransient<UploadViewModel>();
		builder.Services.AddTransient<AnalysisViewModel>();
		builder.Services.AddTransient<GenerationViewModel>();
		builder.Services.AddTransient<StemsViewModel>();
		builder.Services.AddTransient<JobsViewModel>();
		builder.Services.AddTransient<AudioFileDetailViewModel>();
		builder.Services.AddTransient<MixingViewModel>();

		// Register Pages
		builder.Services.AddTransient<MainPage>();
		builder.Services.AddTransient<UploadPage>();
		builder.Services.AddTransient<AnalysisPage>();
		builder.Services.AddTransient<GenerationPage>();
		builder.Services.AddTransient<StemsPage>();
		builder.Services.AddTransient<JobsPage>();
		builder.Services.AddTransient<AudioFileDetailPage>();
		builder.Services.AddTransient<MixingPage>();

		// Converters
		builder.Services.AddSingleton<IsNotNullOrEmptyConverter>();

		return builder.Build();
	}
}
