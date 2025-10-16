using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using DirectML.AI.Models;
using DirectML.AI.Inference;

namespace DirectML.AI.Core
{
    /// <summary>
    /// Base implementation of the AI service
    /// </summary>
    public class AIServiceBase : IAIService
    {
        private readonly ILogger<AIServiceBase> _logger;
        private readonly IOptionsMonitor<AIConfiguration> _configMonitor;
        private readonly IInferenceProvider _inferenceProvider;
        
        private bool _isInitialized;
        private AIConfiguration _currentConfig;

        public AIServiceBase(
            ILogger<AIServiceBase> logger,
            IOptionsMonitor<AIConfiguration> configMonitor,
            DeviceManager deviceManager,
            IModelManager modelManager,
            IInferenceProvider inferenceProvider)
        {
            _logger = logger;
            _configMonitor = configMonitor;
            DeviceManager = deviceManager;
            ModelManager = modelManager;
            _inferenceProvider = inferenceProvider;
            _currentConfig = new AIConfiguration();
        }

        public DeviceManager DeviceManager { get; }
        public IModelManager ModelManager { get; }
        public bool IsInitialized => _isInitialized;
        public AIConfiguration Configuration => _currentConfig;

        public async Task<bool> InitializeAsync(AIConfiguration configuration, CancellationToken cancellationToken = default)
        {
            try
            {
                _logger.LogInformation("Initializing DirectML.AI service");
                _currentConfig = configuration;

                // Initialize device manager
                if (configuration.DirectML.Enabled)
                {
                    var deviceInitialized = await DeviceManager.InitializeAsync(configuration.DirectML, cancellationToken);
                    if (!deviceInitialized)
                    {
                        _logger.LogWarning("DirectML device initialization failed");
                    }
                }

                // Initialize model manager
                await ModelManager.InitializeAsync(configuration.Models, cancellationToken);

                // Initialize inference provider
                await _inferenceProvider.InitializeAsync(cancellationToken);

                _isInitialized = true;
                _logger.LogInformation("DirectML.AI service initialized successfully");
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to initialize DirectML.AI service");
                return false;
            }
        }

        public async Task ShutdownAsync(CancellationToken cancellationToken = default)
        {
            try
            {
                _logger.LogInformation("Shutting down DirectML.AI service");

                // Cleanup services
                await DeviceManager.ShutdownAsync(cancellationToken);

                _isInitialized = false;
                _logger.LogInformation("DirectML.AI service shut down successfully");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during DirectML.AI service shutdown");
            }
        }
    }
}
