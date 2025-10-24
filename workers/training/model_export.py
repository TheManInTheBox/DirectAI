"""
Model Export Pipeline for MusicGen
Exports trained MusicGen models to TorchScript and ONNX for optimized deployment
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import json

import torch
import torch.onnx
from transformers import MusicgenForConditionalGeneration, AutoProcessor
from peft import PeftModel
import onnx
import onnxruntime as ort

logger = logging.getLogger(__name__)


class MusicGenExporter:
    """
    Export MusicGen models to deployment-ready formats
    
    Supports:
    - TorchScript (JIT compilation)
    - ONNX (cross-platform inference)
    - Quantization for size reduction
    """
    
    def __init__(
        self,
        model: torch.nn.Module,
        processor: AutoProcessor,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        """
        Initialize the exporter
        
        Args:
            model: Trained MusicGen model (base or PEFT)
            processor: Hugging Face processor
            device: Device to export from
        """
        self.model = model
        self.processor = processor
        self.device = device
        
        self.model.to(device)
        self.model.eval()
        
        logger.info(f"Initialized MusicGen exporter on device: {device}")
    
    def export_to_torchscript(
        self,
        output_path: Path,
        optimize_for_mobile: bool = False
    ) -> Path:
        """
        Export model to TorchScript format
        
        TorchScript benefits:
        - Faster inference than Python
        - Can run without Python interpreter
        - Better optimization opportunities
        - Mobile deployment support
        
        Args:
            output_path: Path to save TorchScript model
            optimize_for_mobile: Whether to optimize for mobile deployment
            
        Returns:
            Path to saved TorchScript model
        """
        logger.info("Exporting model to TorchScript...")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Merge LoRA weights into base model if using PEFT
            if isinstance(self.model, PeftModel):
                logger.info("Merging LoRA weights into base model for TorchScript export...")
                self.model = self.model.merge_and_unload()
            
            # Set model to eval mode
            self.model.eval()
            
            # Create example inputs for tracing
            example_text = "upbeat rock music with electric guitar"
            inputs = self.processor(
                text=[example_text],
                padding=True,
                return_tensors="pt"
            )
            
            # Move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Trace the model
            with torch.no_grad():
                traced_model = torch.jit.trace(
                    self.model,
                    example_inputs=(
                        inputs["input_ids"],
                        inputs["attention_mask"]
                    ),
                    strict=False
                )
            
            # Optimize for inference
            if optimize_for_mobile:
                logger.info("Optimizing TorchScript for mobile...")
                from torch.utils.mobile_optimizer import optimize_for_mobile
                traced_model = optimize_for_mobile(traced_model)
            else:
                traced_model = torch.jit.optimize_for_inference(traced_model)
            
            # Save the model
            torch.jit.save(traced_model, str(output_path))
            
            logger.info(f"TorchScript model saved to {output_path}")
            logger.info(f"Model size: {output_path.stat().st_size / (1024**2):.2f} MB")
            
            # Save processor config
            processor_path = output_path.parent / "processor_config.json"
            self.processor.save_pretrained(str(output_path.parent))
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to export to TorchScript: {e}")
            raise RuntimeError(f"TorchScript export failed: {e}")
    
    def export_to_onnx(
        self,
        output_path: Path,
        opset_version: int = 14,
        dynamic_axes: Optional[Dict] = None,
        quantize: bool = False
    ) -> Path:
        """
        Export model to ONNX format
        
        ONNX benefits:
        - Cross-platform inference (ONNX Runtime)
        - Optimization for different backends
        - Quantization support
        - Broad hardware support
        
        Args:
            output_path: Path to save ONNX model
            opset_version: ONNX opset version
            dynamic_axes: Dynamic axes for variable input sizes
            quantize: Whether to quantize the model
            
        Returns:
            Path to saved ONNX model
        """
        logger.info("Exporting model to ONNX...")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Merge LoRA weights if using PEFT
            if isinstance(self.model, PeftModel):
                logger.info("Merging LoRA weights for ONNX export...")
                self.model = self.model.merge_and_unload()
            
            # Set model to eval mode
            self.model.eval()
            
            # Create example inputs
            example_text = "upbeat rock music with electric guitar"
            inputs = self.processor(
                text=[example_text],
                padding=True,
                return_tensors="pt"
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Define dynamic axes if not provided
            if dynamic_axes is None:
                dynamic_axes = {
                    "input_ids": {0: "batch_size", 1: "sequence_length"},
                    "attention_mask": {0: "batch_size", 1: "sequence_length"},
                    "audio_values": {0: "batch_size", 1: "audio_length"}
                }
            
            # Export to ONNX
            torch.onnx.export(
                self.model,
                args=(inputs["input_ids"], inputs["attention_mask"]),
                f=str(output_path),
                export_params=True,
                opset_version=opset_version,
                do_constant_folding=True,
                input_names=["input_ids", "attention_mask"],
                output_names=["audio_values"],
                dynamic_axes=dynamic_axes,
                verbose=False
            )
            
            logger.info(f"ONNX model saved to {output_path}")
            
            # Validate ONNX model
            self._validate_onnx_model(output_path)
            
            # Quantize if requested
            if quantize:
                quantized_path = output_path.parent / f"{output_path.stem}_quantized.onnx"
                self._quantize_onnx_model(output_path, quantized_path)
                output_path = quantized_path
            
            logger.info(f"Final ONNX model size: {output_path.stat().st_size / (1024**2):.2f} MB")
            
            # Save processor config
            self.processor.save_pretrained(str(output_path.parent))
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to export to ONNX: {e}")
            raise RuntimeError(f"ONNX export failed: {e}")
    
    def _validate_onnx_model(self, onnx_path: Path):
        """Validate ONNX model structure"""
        try:
            # Load and check the model
            onnx_model = onnx.load(str(onnx_path))
            onnx.checker.check_model(onnx_model)
            
            logger.info("ONNX model validation passed")
            
        except Exception as e:
            logger.warning(f"ONNX validation warning: {e}")
    
    def _quantize_onnx_model(self, input_path: Path, output_path: Path):
        """
        Quantize ONNX model to reduce size
        
        Converts weights from FP32 to INT8 for:
        - Smaller model size (4x reduction)
        - Faster inference on CPU
        - Lower memory usage
        """
        try:
            from onnxruntime.quantization import quantize_dynamic, QuantType
            
            logger.info("Quantizing ONNX model to INT8...")
            
            quantize_dynamic(
                model_input=str(input_path),
                model_output=str(output_path),
                weight_type=QuantType.QUInt8,
                optimize_model=True
            )
            
            # Compare sizes
            orig_size = input_path.stat().st_size / (1024**2)
            quant_size = output_path.stat().st_size / (1024**2)
            reduction = (1 - quant_size / orig_size) * 100
            
            logger.info(f"Quantization complete:")
            logger.info(f"  Original size: {orig_size:.2f} MB")
            logger.info(f"  Quantized size: {quant_size:.2f} MB")
            logger.info(f"  Reduction: {reduction:.1f}%")
            
        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            raise RuntimeError(f"ONNX quantization failed: {e}")
    
    def export_all_formats(
        self,
        output_dir: Path,
        export_torchscript: bool = True,
        export_onnx: bool = True,
        quantize_onnx: bool = True
    ) -> Dict[str, Path]:
        """
        Export model to all supported formats
        
        Args:
            output_dir: Base output directory
            export_torchscript: Whether to export TorchScript
            export_onnx: Whether to export ONNX
            quantize_onnx: Whether to quantize ONNX model
            
        Returns:
            Dictionary mapping format names to output paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exported_paths = {}
        
        # Export TorchScript
        if export_torchscript:
            try:
                ts_path = output_dir / "model.pt"
                exported_paths["torchscript"] = self.export_to_torchscript(ts_path)
            except Exception as e:
                logger.error(f"TorchScript export failed: {e}")
        
        # Export ONNX
        if export_onnx:
            try:
                onnx_path = output_dir / "model.onnx"
                exported_paths["onnx"] = self.export_to_onnx(
                    onnx_path,
                    quantize=quantize_onnx
                )
            except Exception as e:
                logger.error(f"ONNX export failed: {e}")
        
        # Save export metadata
        metadata = {
            "timestamp": torch.datetime.now().isoformat(),
            "base_model": "facebook/musicgen-small",
            "formats": list(exported_paths.keys()),
            "paths": {k: str(v) for k, v in exported_paths.items()}
        }
        
        with open(output_dir / "export_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Export complete. Formats: {list(exported_paths.keys())}")
        
        return exported_paths


class ONNXInferenceEngine:
    """
    ONNX Runtime inference engine for exported models
    
    Provides optimized inference using ONNX Runtime with support for:
    - CPU and GPU execution
    - Quantized models
    - Batched inference
    """
    
    def __init__(
        self,
        onnx_model_path: Path,
        processor_path: Path,
        use_gpu: bool = False
    ):
        """
        Initialize ONNX inference engine
        
        Args:
            onnx_model_path: Path to ONNX model file
            processor_path: Path to processor config directory
            use_gpu: Whether to use GPU acceleration
        """
        self.model_path = onnx_model_path
        
        # Set execution providers
        if use_gpu and 'CUDAExecutionProvider' in ort.get_available_providers():
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        else:
            providers = ['CPUExecutionProvider']
        
        # Create inference session
        self.session = ort.InferenceSession(
            str(onnx_model_path),
            providers=providers
        )
        
        # Load processor
        self.processor = AutoProcessor.from_pretrained(str(processor_path))
        
        logger.info(f"ONNX Runtime session created with providers: {providers}")
    
    def generate(
        self,
        prompt: str,
        max_length: int = 1024,
        temperature: float = 1.0
    ) -> torch.Tensor:
        """
        Generate audio from text prompt using ONNX model
        
        Args:
            prompt: Text description of desired music
            max_length: Maximum generation length
            temperature: Sampling temperature
            
        Returns:
            Generated audio tensor
        """
        # Tokenize input
        inputs = self.processor(
            text=[prompt],
            padding=True,
            return_tensors="np"
        )
        
        # Run inference
        outputs = self.session.run(
            None,
            {
                "input_ids": inputs["input_ids"],
                "attention_mask": inputs["attention_mask"]
            }
        )
        
        # Convert to torch tensor
        audio_values = torch.from_numpy(outputs[0])
        
        return audio_values


def export_trained_model_from_checkpoint(
    checkpoint_path: Path,
    output_dir: Path,
    base_model_name: str = "facebook/musicgen-small",
    formats: list = ["torchscript", "onnx"]
) -> Dict[str, Path]:
    """
    Utility function to export a trained model from checkpoint
    
    Args:
        checkpoint_path: Path to LoRA checkpoint
        output_dir: Output directory for exported models
        base_model_name: Base model name
        formats: List of formats to export ("torchscript", "onnx")
        
    Returns:
        Dictionary of exported model paths
    """
    logger.info(f"Loading model from checkpoint: {checkpoint_path}")
    
    # Load base model
    base_model = MusicgenForConditionalGeneration.from_pretrained(base_model_name)
    
    # Load LoRA adapters
    model = PeftModel.from_pretrained(base_model, str(checkpoint_path))
    
    # Load processor
    processor = AutoProcessor.from_pretrained(base_model_name)
    
    # Create exporter
    exporter = MusicGenExporter(model, processor)
    
    # Export to requested formats
    exported = exporter.export_all_formats(
        output_dir=output_dir,
        export_torchscript="torchscript" in formats,
        export_onnx="onnx" in formats
    )
    
    logger.info(f"Model exported successfully to {output_dir}")
    
    return exported


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Load a trained model and export it
    # checkpoint_path = Path("./checkpoints/final_model")
    # output_dir = Path("./exported_models")
    #
    # exported_models = export_trained_model_from_checkpoint(
    #     checkpoint_path=checkpoint_path,
    #     output_dir=output_dir,
    #     formats=["torchscript", "onnx"]
    # )
    #
    # print(f"Exported models: {exported_models}")
    
    print("Model export pipeline ready")
