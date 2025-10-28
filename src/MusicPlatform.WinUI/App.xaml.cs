using Microsoft.UI.Xaml.Navigation;
using Microsoft.Extensions.DependencyInjection;
using MusicPlatform.WinUI.Services;
using MusicPlatform.WinUI.ViewModels;
using MusicPlatform.WinUI.Views;

namespace MusicPlatform.WinUI
{
    public partial class App : Application
    {
        public static Window? MainWindow { get; private set; }
        public static IServiceProvider Services { get; private set; } = null!;
        private LoadingWindow? _loadingWindow;

        public App()
        {
            this.InitializeComponent();
        }

        protected override async void OnLaunched(LaunchActivatedEventArgs e)
        {
            Console.WriteLine("OnLaunched: Starting application...");
            System.Diagnostics.Debug.WriteLine("OnLaunched: Starting application...");

            try
            {
                // Show loading window immediately
                _loadingWindow = new LoadingWindow();
                _loadingWindow.Activate();
                Console.WriteLine("OnLaunched: Loading window created and activated");
                System.Diagnostics.Debug.WriteLine("OnLaunched: Loading window created and activated");

                // Initialize everything in background with proper data loading
                await InitializeApplicationAsync();

                // Create main window
                MainWindow = new MainWindow();
                MainWindow.Activate();
                Console.WriteLine("OnLaunched: Main window created and activated");
                System.Diagnostics.Debug.WriteLine("OnLaunched: Main window created and activated");

                // Close loading window
                _loadingWindow?.Close();
                _loadingWindow = null;
                Console.WriteLine("OnLaunched: Application launch completed");
                System.Diagnostics.Debug.WriteLine("OnLaunched: Application launch completed");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"OnLaunched: Error - {ex.Message}");
                Console.WriteLine($"OnLaunched: StackTrace - {ex.StackTrace}");
                System.Diagnostics.Debug.WriteLine($"OnLaunched: Error - {ex.Message}");
                System.Diagnostics.Debug.WriteLine($"OnLaunched: StackTrace - {ex.StackTrace}");
            }
        }

        private async Task InitializeApplicationAsync()
        {
            System.Diagnostics.Debug.WriteLine("InitializeApplicationAsync: Starting initialization...");
            try
            {
                // Step 1: Configure Services
                _loadingWindow?.UpdateStatus("Configuring services...");
                _loadingWindow?.UpdateStep(1);
                System.Diagnostics.Debug.WriteLine("InitializeApplicationAsync: Step 1 - Configuring services");
                
                ConfigureServices();
                _loadingWindow?.UpdateStep(1, completed: true);
                System.Diagnostics.Debug.WriteLine("InitializeApplicationAsync: Step 1 completed");

                // Step 2: Connect to API
                _loadingWindow?.UpdateStatus("Connecting to API...");
                _loadingWindow?.UpdateStep(2);
                
                // Test API connection with timeout
                var apiClient = Services.GetRequiredService<MusicPlatformApiClient>();
                try
                {
                    System.Diagnostics.Debug.WriteLine("Testing API connection with 10 second timeout...");
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
                    var healthCheck = await apiClient.GetAllAudioFilesAsync().WaitAsync(cts.Token);
                    System.Diagnostics.Debug.WriteLine("API connection successful");
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"API connection test failed: {ex.Message}");
                    // Continue anyway - might be offline
                }
                _loadingWindow?.UpdateStep(2, completed: true);

                // Step 3: Load Audio Library Data (without ViewModels yet)
                _loadingWindow?.UpdateStatus("Loading audio library...");
                _loadingWindow?.UpdateStep(3);
                
                var libraryCacheService = Services.GetRequiredService<AudioLibraryCacheService>();
                
                // Load audio files with timeout
                List<MusicPlatform.WinUI.Models.AudioFileDto>? audioFiles = null;
                var stemCounts = new Dictionary<Guid, int>();
                
                try
                {
                    System.Diagnostics.Debug.WriteLine("Loading audio files with 15 second timeout...");
                    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
                    audioFiles = await apiClient.GetAllAudioFilesAsync().WaitAsync(cts.Token);
                    System.Diagnostics.Debug.WriteLine($"Loaded {audioFiles?.Count ?? 0} audio files");
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"Failed to load audio files: {ex.Message}");
                    audioFiles = null;
                }
                
                if (audioFiles != null && audioFiles.Any())
                {
                    System.Diagnostics.Debug.WriteLine($"Loading stem counts for {audioFiles.Count} files concurrently...");
                    
                    // Load stem counts concurrently with timeout per file
                    var stemTasks = audioFiles.Select(async audioFile =>
                    {
                        try
                        {
                            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                            var stems = await apiClient.GetStemsByAudioFileAsync(audioFile.Id).WaitAsync(cts.Token);
                            return new { AudioFile = audioFile, StemCount = stems?.Count() ?? 0 };
                        }
                        catch (Exception ex)
                        {
                            System.Diagnostics.Debug.WriteLine($"Error loading stems for {audioFile.OriginalFileName}: {ex.Message}");
                            return new { AudioFile = audioFile, StemCount = 0 };
                        }
                    });

                    // Wait for all stem loading with overall timeout
                    try
                    {
                        using var overallCts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
                        var results = await Task.WhenAll(stemTasks).WaitAsync(overallCts.Token);
                        
                        foreach (var result in results)
                        {
                            stemCounts[result.AudioFile.Id] = result.StemCount;
                        }
                        System.Diagnostics.Debug.WriteLine($"Loaded stem counts for {stemCounts.Count} files");
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"Timeout loading stem counts: {ex.Message}");
                        // Use what we have so far
                    }
                    
                    // Cache the data for immediate access
                    if (audioFiles != null && audioFiles.Any())
                    {
                        await libraryCacheService.SaveCacheAsync(audioFiles, stemCounts);
                        System.Diagnostics.Debug.WriteLine($"STARTUP: Cached {audioFiles.Count} audio files with {stemCounts.Count} stem counts");
                        Console.WriteLine($"STARTUP: Cached {audioFiles.Count} audio files with {stemCounts.Count} stem counts");
                    }
                    else
                    {
                        System.Diagnostics.Debug.WriteLine("STARTUP: No audio files to cache");
                        Console.WriteLine("STARTUP: No audio files to cache");
                    }
                }
                else
                {
                    System.Diagnostics.Debug.WriteLine("STARTUP: No audio files loaded or API failed");
                    Console.WriteLine("STARTUP: No audio files loaded or API failed");
                }
                
                _loadingWindow?.UpdateStatus("Audio library loaded successfully");
                _loadingWindow?.UpdateStep(3, completed: true);

                // Step 4: Configure ViewModels with Pre-loaded Data
                _loadingWindow?.UpdateStatus("Initializing ViewModels...");
                _loadingWindow?.UpdateStep(4);
                
                ConfigureViewModels();
                System.Diagnostics.Debug.WriteLine("ViewModels configured");
                
                // Pre-load ALL ViewModels so every page is instantly ready
                try
                {
                    System.Diagnostics.Debug.WriteLine("Pre-loading ALL ViewModels for instant page access...");
                    Console.WriteLine("Pre-loading ALL ViewModels for instant page access...");
                    
                    // 1. MixingViewModel - This is the critical one for Mix page
                    _loadingWindow?.UpdateStatus("Pre-loading Mix page...");
                    System.Diagnostics.Debug.WriteLine("STARTUP: Getting MixingViewModel...");
                    Console.WriteLine("STARTUP: Getting MixingViewModel...");
                    
                    var mixingViewModel = Services.GetRequiredService<MixingViewModel>();
                    System.Diagnostics.Debug.WriteLine("STARTUP: Loading MixingViewModel data...");
                    Console.WriteLine("STARTUP: Loading MixingViewModel data...");
                    
                    await mixingViewModel.LoadAudioFilesCompletelyAsync();
                    System.Diagnostics.Debug.WriteLine($"STARTUP: MixingViewModel loaded - {mixingViewModel.AvailableAudioFiles.Count} files");
                    Console.WriteLine($"STARTUP: MixingViewModel loaded - {mixingViewModel.AvailableAudioFiles.Count} files");
                    
                    // 2. Load other ViewModels quickly without blocking
                    _loadingWindow?.UpdateStatus("Pre-loading other pages...");
                    
                    try
                    {
                        var audioLibraryViewModel = Services.GetRequiredService<AudioLibraryViewModel>();
                        await audioLibraryViewModel.LoadAudioFilesInternalAsync();
                        System.Diagnostics.Debug.WriteLine("AudioLibraryViewModel loaded");
                        Console.WriteLine("AudioLibraryViewModel loaded");
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"AudioLibraryViewModel failed: {ex.Message}");
                        Console.WriteLine($"AudioLibraryViewModel failed: {ex.Message}");
                    }
                    
                    try
                    {
                        var jobsViewModel = Services.GetRequiredService<JobsViewModel>();
                        await jobsViewModel.LoadJobsInternalAsync();
                        jobsViewModel.StartPeriodicRefresh();
                        System.Diagnostics.Debug.WriteLine("JobsViewModel loaded");
                        Console.WriteLine("JobsViewModel loaded");
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"JobsViewModel failed: {ex.Message}");
                        Console.WriteLine($"JobsViewModel failed: {ex.Message}");
                    }
                    
                    try
                    {
                        var dashboardViewModel = Services.GetRequiredService<DashboardViewModel>();
                        await dashboardViewModel.LoadStatsInternalAsync();
                        System.Diagnostics.Debug.WriteLine("DashboardViewModel loaded");
                        Console.WriteLine("DashboardViewModel loaded");
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"DashboardViewModel failed: {ex.Message}");
                        Console.WriteLine($"DashboardViewModel failed: {ex.Message}");
                    }
                    
                    // Initialize GenerationViewModel (no loading needed)
                    var generationViewModel = Services.GetRequiredService<GenerationViewModel>();
                    System.Diagnostics.Debug.WriteLine("GenerationViewModel initialized");
                    Console.WriteLine("GenerationViewModel initialized");
                    
                    System.Diagnostics.Debug.WriteLine("ALL ViewModels completed!");
                    Console.WriteLine("ALL ViewModels completed!");
                    
                    // Final verification that MixingViewModel has data
                    System.Diagnostics.Debug.WriteLine($"FINAL CHECK: MixingViewModel has {mixingViewModel.AvailableAudioFiles.Count} audio files loaded");
                    Console.WriteLine($"FINAL CHECK: MixingViewModel has {mixingViewModel.AvailableAudioFiles.Count} audio files loaded");
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"ViewModel pre-loading timed out or failed: {ex.Message}");
                    Console.WriteLine($"ViewModel pre-loading timed out or failed: {ex.Message}");
                    // Continue anyway - ViewModels can load data later when accessed
                }
                
                _loadingWindow?.UpdateStatus("All pages pre-loaded successfully");
                _loadingWindow?.UpdateStep(4, completed: true);

                // Start SignalR connection in background
                var signalR = Services.GetRequiredService<SignalRService>();
                _ = signalR.StartAsync(); // Fire and forget

                // Final status
                _loadingWindow?.UpdateStatus("Ready to launch!");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Initialization error: {ex.Message}");
                _loadingWindow?.UpdateStatus($"Error: {ex.Message}");
            }
        }

        private void ConfigureServices()
        {
            var services = new ServiceCollection();
            // Resolve API base URL (env var -> .azure/dev/.env -> localhost)
            var baseUrl = Config.ResolveBaseApiUrl();

            // HTTP Client with base address
            services.AddSingleton(new HttpClient
            {
                BaseAddress = new Uri(baseUrl),
                Timeout = TimeSpan.FromMinutes(5)
            });

            // Services only - ViewModels added after loading
            services.AddSingleton<MusicPlatformApiClient>();
            services.AddSingleton(sp => new SignalRService(baseUrl));
            services.AddSingleton<AudioCacheService>();
            services.AddSingleton<AudioLibraryCacheService>();
            services.AddSingleton<AudioPlaybackService>();
            services.AddSingleton<WaveformService>();
            services.AddSingleton<FastWaveformService>();

            Services = services.BuildServiceProvider();
        }

        private void ConfigureViewModels()
        {
            // Create new service collection with existing services plus ViewModels
            var services = new ServiceCollection();
            var baseUrl = Config.ResolveBaseApiUrl();

            // Re-add all services
            services.AddSingleton(new HttpClient
            {
                BaseAddress = new Uri(baseUrl),
                Timeout = TimeSpan.FromMinutes(5)
            });
            services.AddSingleton<MusicPlatformApiClient>();
            services.AddSingleton(sp => new SignalRService(baseUrl));
            services.AddSingleton<AudioCacheService>();
            services.AddSingleton<AudioLibraryCacheService>();
            services.AddSingleton<AudioPlaybackService>();
            services.AddSingleton<WaveformService>();
            services.AddSingleton<FastWaveformService>();

            // Now add ViewModels after data is loaded
            services.AddSingleton<DashboardViewModel>();
            services.AddSingleton<AudioLibraryViewModel>();
            services.AddSingleton<GenerationViewModel>();
            services.AddSingleton<JobsViewModel>();
            services.AddSingleton<MixingViewModel>();

            // Replace Services with new provider that includes ViewModels
            Services = services.BuildServiceProvider();
        }
    }
}
