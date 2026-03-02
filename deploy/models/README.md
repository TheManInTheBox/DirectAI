# DirectAI Model Deployment Config Schema
#
# Each YAML file in this directory declares a model deployment.
# The API server reads these to build its routing table.
# The Helm chart reads these to create Kubernetes Deployments + Services.
#
# Schema version: directai/v1
# Kind: ModelDeployment
#
# Fields:
#   metadata.name        — Unique model identifier (used in K8s resource names)
#   spec.displayName     — Human-readable name (returned by GET /v1/models)
#   spec.ownedBy         — Model provider/org (returned by GET /v1/models)
#   spec.modality        — One of: chat, embedding, transcription
#   spec.engine.type     — Inference engine: tensorrt-llm, onnxruntime
#   spec.engine.image    — Container image for the inference backend
#   spec.engine.weightsUri — Blob Storage URI for model weights
#   spec.engine.engineUri  — Blob Storage URI for compiled engine (optional, TRT-LLM)
#   spec.engine.maxBatchSize — Max dynamic batch size (embeddings/reranking)
#   spec.hardware.gpuSku — Azure VM SKU for node pool selection
#   spec.hardware.gpuCount — GPUs per replica (determines TP degree for TRT-LLM)
#   spec.hardware.nvmeCacheEnabled — Use node-local NVMe for weight caching
#   spec.scaling.tier    — always-warm or scale-to-zero
#   spec.scaling.minReplicas — Floor replica count
#   spec.scaling.maxReplicas — Ceiling replica count
#   spec.scaling.targetConcurrency — Inflight requests per replica before scale-up
#   spec.api.aliases     — Model name strings clients can use in API requests
