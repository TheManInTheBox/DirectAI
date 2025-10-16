using System;
using System.Threading;
using System.Threading.Tasks;
using DirectML.AI.Models;

namespace DirectML.AI.Core
{
    /// <summary>
    /// Main AI service interface providing unified access to inference, training, and search capabilities
    /// </summary>
    public interface IAIService
    {
        /// <summary>
        /// Initializes the AI service with the specified configuration
        /// </summary>
        Task<bool> InitializeAsync(AIConfiguration configuration, CancellationToken cancellationToken = default);

        /// <summary>
        /// Gets the current device manager
        /// </summary>
        DeviceManager DeviceManager { get; }

        /// <summary>
        /// Gets the model manager
        /// </summary>
        IModelManager ModelManager { get; }

        /// <summary>
        /// Checks if the service is initialized and ready
        /// </summary>
        bool IsInitialized { get; }

        /// <summary>
        /// Gets the current configuration
        /// </summary>
        AIConfiguration Configuration { get; }

        /// <summary>
        /// Shuts down the AI service and releases resources
        /// </summary>
        Task ShutdownAsync(CancellationToken cancellationToken = default);
    }
}
