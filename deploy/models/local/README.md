# ============================================================================
# Local Dev Model Configs
# ============================================================================
#
# These YAMLs point at localhost backends (Ollama) for local development.
# They use spec.engine.backendUrl to override the K8s service DNS pattern.
#
# Setup:
#   1. Install Ollama: winget install Ollama.Ollama (Windows) / brew install ollama (Mac)
#   2. Pull models:
#        ollama pull llama3.2:3b
#        ollama pull nomic-embed-text
#   3. Ollama serves at http://localhost:11434 (auto-starts on install)
#   4. Run the API server:
#        cd src/api-server
#        $env:DIRECTAI_MODEL_CONFIG_DIR = "../../deploy/models/local"
#        python -m uvicorn app.main:app --reload
#   5. Test:
#        curl http://localhost:8000/v1/models
#        curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"Hi"}]}'
#        curl http://localhost:8000/v1/embeddings -H "Content-Type: application/json" -d '{"model":"nomic-embed-text","input":"Hello world"}'
#
# GPU Notes (RTX A2000 4GB VRAM / 16GB shared):
#   - llama3.2:3b (Q4): ~2GB VRAM — fits comfortably
#   - nomic-embed-text: ~275MB VRAM — fits easily
#   - If you have more VRAM, try llama3.1:8b or phi3:mini instead
