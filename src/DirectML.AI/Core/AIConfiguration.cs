using System;
using System.Collections.Generic;

namespace DirectML.AI.Core
{
    /// <summary>
    /// Configuration settings for the AI platform
    /// </summary>
    public class AIConfiguration
    {
        /// <summary>
        /// DirectML device configuration
        /// </summary>
        public DirectMLConfig DirectML { get; set; } = new();

        /// <summary>
        /// Model management configuration
        /// </summary>
        public ModelConfig Models { get; set; } = new();

        /// <summary>
        /// Vector database configuration
        /// </summary>
        public VectorDBConfig VectorDatabase { get; set; } = new();

        /// <summary>
        /// Semantic search configuration
        /// </summary>
        public SemanticSearchConfig SemanticSearch { get; set; } = new();

        /// <summary>
        /// Training configuration
        /// </summary>
        public TrainingConfig Training { get; set; } = new();

        /// <summary>
        /// Additional custom properties
        /// </summary>
        public Dictionary<string, object> Properties { get; set; } = new();
    }

    public class DirectMLConfig
    {
        public bool Enabled { get; set; } = true;
        public int DeviceId { get; set; } = 0;
        public long MaxMemoryMB { get; set; } = 4096;
        public bool EnableDebugLayer { get; set; } = false;
    }

    public class ModelConfig
    {
        public string CacheDirectory { get; set; } = "models";
        public bool EnableCache { get; set; } = true;
        public int MaxCachedModels { get; set; } = 10;
        public long MaxModelSizeMB { get; set; } = 2048;
    }

    public class VectorDBConfig
    {
        public int DefaultDimensions { get; set; } = 384;
        public string StoragePath { get; set; } = "vectordb";
        public bool InMemoryOnly { get; set; } = true;
        public int MaxVectors { get; set; } = 1000000;
        public float DefaultSimilarityThreshold { get; set; } = 0.7f;
    }

    public class SemanticSearchConfig
    {
        public string EmbeddingModel { get; set; } = "all-MiniLM-L6-v2";
        public int DefaultTopK { get; set; } = 10;
        public bool EnableTextPreprocessing { get; set; } = true;
        public int MaxTextLength { get; set; } = 8192;
    }

    public class TrainingConfig
    {
        public string OutputDirectory { get; set; } = "training_output";
        public int DefaultBatchSize { get; set; } = 8;
        public float DefaultLearningRate { get; set; } = 1e-4f;
        public int DefaultEpochs { get; set; } = 3;
        public bool EnableCheckpoints { get; set; } = true;
    }
}
