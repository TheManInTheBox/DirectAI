using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Configuration;
using DirectML.AI.Core;
using DirectML.AI.Inference;
using DirectML.AI.Models;
using DirectML.AI.DirectML;

namespace DirectML.AI.Extensions
{
    /// <summary>
    /// Extension methods for registering DirectML.AI services
    /// </summary>
    public static class ServiceCollectionExtensions
    {
        /// <summary>
        /// Adds the complete DirectML.AI platform
        /// </summary>
        public static IServiceCollection AddDirectMLAI(this IServiceCollection services, IConfiguration configuration)
        {
            // Bind configuration
            services.Configure<AIConfiguration>(configuration.GetSection("DirectMLAI"));

            // Core services
            services.AddSingleton<IAIService, AIServiceBase>();
            services.AddSingleton<DeviceManager>();
            services.AddSingleton<DirectMLDeviceManager>();

            // Model management
            services.AddSingleton<IModelManager, ModelManager>();
            services.AddSingleton<ModelLoader>();
            services.AddSingleton<ModelCache>();

            // Inference
            services.AddSingleton<IInferenceProvider, DirectMLInferenceProvider>();

            return services;
        }

        /// <summary>
        /// Adds DirectML.AI with action-based configuration
        /// </summary>
        public static IServiceCollection AddDirectMLAI(this IServiceCollection services, Action<AIConfiguration> configure)
        {
            services.Configure(configure);
            return services.AddDirectMLAI();
        }

        /// <summary>
        /// Adds only inference capabilities
        /// </summary>
        public static IServiceCollection AddDirectMLInference(this IServiceCollection services)
        {
            services.AddSingleton<IInferenceProvider, DirectMLInferenceProvider>();
            services.AddSingleton<IModelManager, ModelManager>();
            services.AddSingleton<ModelLoader>();
            services.AddSingleton<ModelCache>();
            services.AddSingleton<DeviceManager>();
            services.AddSingleton<DirectMLDeviceManager>();

            return services;
        }

        // Private method for core services without configuration
        private static IServiceCollection AddDirectMLAI(this IServiceCollection services)
        {
            // Core services
            services.AddSingleton<IAIService, AIServiceBase>();
            services.AddSingleton<DeviceManager>();

            // Model management
            services.AddSingleton<IModelManager, ModelManager>();
            services.AddSingleton<ModelLoader>();
            services.AddSingleton<ModelCache>();

            // Inference
            services.AddSingleton<IInferenceProvider, DirectMLInferenceProvider>();

            return services;
        }
    }
}
