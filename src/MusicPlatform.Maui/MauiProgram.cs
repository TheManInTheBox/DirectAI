using Microsoft.Extensions.Logging;
using MusicPlatform.Maui.Services;
using MusicPlatform.Maui.Pages;
using MusicPlatform.Maui.ViewModels;

namespace MusicPlatform.Maui;

public static class MauiProgram
{
	public static MauiApp CreateMauiApp()
	{
		var builder = MauiApp.CreateBuilder();
		builder
			.UseMauiApp<App>()
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
		});

		// Register ViewModels
		builder.Services.AddTransient<MainViewModel>();
		builder.Services.AddTransient<UploadViewModel>();
		builder.Services.AddTransient<AnalysisViewModel>();
		builder.Services.AddTransient<GenerationViewModel>();
		builder.Services.AddTransient<StemsViewModel>();

		// Register Pages
		builder.Services.AddTransient<MainPage>();
		builder.Services.AddTransient<UploadPage>();
		builder.Services.AddTransient<AnalysisPage>();
		builder.Services.AddTransient<GenerationPage>();
		builder.Services.AddTransient<StemsPage>();

		return builder.Build();
	}
}
