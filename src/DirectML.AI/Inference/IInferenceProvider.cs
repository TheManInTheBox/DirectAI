using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using DirectML.AI.Models;

namespace DirectML.AI.Inference
{
    /// <summary>
    /// Interface for ML inference operations
    /// </summary>
    public interface IInferenceProvider
    {
        /// <summary>
        /// Initializes the inference provider
        /// </summary>
        Task<bool> InitializeAsync(CancellationToken cancellationToken = default);

        /// <summary>
        /// Loads a model for inference
        /// </summary>
        Task<bool> LoadModelAsync(ModelMetadata model, CancellationToken cancellationToken = default);

        /// <summary>
        /// Executes inference with the loaded model
        /// </summary>
        Task<InferenceResponse> InferAsync(InferenceRequest request, CancellationToken cancellationToken = default);

        /// <summary>
        /// Executes streaming inference
        /// </summary>
        IAsyncEnumerable<InferenceResponse> InferStreamAsync(InferenceRequest request, CancellationToken cancellationToken = default);

        /// <summary>
        /// Unloads the current model
        /// </summary>
        Task UnloadModelAsync(CancellationToken cancellationToken = default);

        /// <summary>
        /// Gets the currently loaded model
        /// </summary>
        ModelMetadata? LoadedModel { get; }

        /// <summary>
        /// Checks if a model is currently loaded
        /// </summary>
        bool IsModelLoaded { get; }

        /// <summary>
        /// Gets inference statistics
        /// </summary>
        InferenceStatistics Statistics { get; }
    }

    /// <summary>
    /// Request object for inference operations
    /// </summary>
    public record InferenceRequest(
        string Input,
        Dictionary<string, object>? Parameters = null,
        InferenceOptions? Options = null);

    /// <summary>
    /// Response object for inference operations
    /// </summary>
    public record InferenceResponse(
        string Output,
        float Confidence,
        TimeSpan ProcessingTime,
        Dictionary<string, object>? Metadata = null);

    /// <summary>
    /// Options for inference operations
    /// </summary>
    public record InferenceOptions(
        int MaxTokens = 512,
        float Temperature = 0.7f,
        float TopP = 0.9f,
        int TopK = 50,
        bool Stream = false);

    /// <summary>
    /// Statistics for inference operations
    /// </summary>
    public record InferenceStatistics(
        long TotalInferences,
        TimeSpan AverageProcessingTime,
        DateTime LastInference,
        long TotalTokensGenerated);
}
