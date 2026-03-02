"""
Utility to download and export a HuggingFace embedding model to ONNX format.

Usage:
    python -m engine.export --model-id BAAI/bge-large-en-v1.5 --output-dir /models

This produces:
    /models/model.onnx         — ONNX model (optimized, FP16 for GPU)
    /models/tokenizer.json     — HuggingFace fast tokenizer
    /models/config.json        — Model config for reference

Requirements (not in main deps — build-time only):
    pip install optimum[onnxruntime-gpu] transformers torch
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def export_model(model_id: str, output_dir: str, *, opset: int = 17, fp16: bool = True) -> None:
    """Export a HuggingFace transformer model to ONNX."""
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from transformers import AutoTokenizer

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    logger.info("Exporting %s to ONNX (opset=%d, fp16=%s) → %s", model_id, opset, fp16, out)

    # Export model
    model = ORTModelForFeatureExtraction.from_pretrained(
        model_id,
        export=True,
    )
    model.save_pretrained(out)
    logger.info("ONNX model saved to %s", out / "model.onnx")

    # Save tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.save_pretrained(out)
    logger.info("Tokenizer saved to %s", out)

    # Optional FP16 conversion
    if fp16:
        try:
            from onnxruntime.transformers import optimizer
            from onnxruntime.transformers.fusion_options import FusionOptions

            opt_options = FusionOptions("bert")
            optimized_model = optimizer.optimize_model(
                str(out / "model.onnx"),
                model_type="bert",
                num_heads=0,  # Auto-detect
                hidden_size=0,  # Auto-detect
                optimization_options=opt_options,
            )
            optimized_model.convert_float_to_float16(
                use_symbolic_shape_infer=True,
                keep_io_types=True,
            )
            fp16_path = out / "model_fp16.onnx"
            optimized_model.save_model_to_file(str(fp16_path))

            # Replace original with FP16
            shutil.move(str(out / "model.onnx"), str(out / "model_fp32.onnx"))
            shutil.move(str(fp16_path), str(out / "model.onnx"))
            logger.info("FP16 optimized model saved (original kept as model_fp32.onnx)")
        except Exception:
            logger.warning("FP16 conversion failed — using FP32 model", exc_info=True)

    logger.info("Export complete: %s", out)


def main():
    parser = argparse.ArgumentParser(description="Export HuggingFace model to ONNX")
    parser.add_argument("--model-id", required=True, help="HuggingFace model ID (e.g., BAAI/bge-large-en-v1.5)")
    parser.add_argument("--output-dir", required=True, help="Output directory for ONNX model and tokenizer")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    parser.add_argument("--no-fp16", action="store_true", help="Skip FP16 conversion")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    export_model(args.model_id, args.output_dir, opset=args.opset, fp16=not args.no_fp16)


if __name__ == "__main__":
    main()
