"""AI and Machine Learning frameworks cache scanner."""

from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir


class AIMLScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "ai_ml"

    @property
    def description(self) -> str:
        return "Scans HuggingFace, PyTorch Hub, Ollama, and local AI model weights"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()

        # 1. HuggingFace Model Hub
        hf_hub = home / ".cache" / "huggingface" / "hub"
        if hf_hub.exists():
            sz = get_dir_size(hf_hub)
            if sz > 100 * 1024 * 1024:  # > 100MB
                findings.append(Finding(
                    id="huggingface_hub_models",
                    title="Hugging Face Cached Model Weights",
                    category=Category.AI_ML,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(hf_hub),
                    size_bytes=sz,
                    description="Pre-trained transformers, LLMs, and embedding weights downloaded via HuggingFace Hub.",
                    cleanup_command=f'rm -rf "{hf_hub}"/*  # or use huggingface-cli delete-cache'
                ))

        # 2. PyTorch Hub Checkpoints
        torch_hub = home / ".cache" / "torch" / "hub"
        if torch_hub.exists():
            sz = get_dir_size(torch_hub)
            if sz > 100 * 1024 * 1024:
                findings.append(Finding(
                    id="torch_hub_checkpoints",
                    title="PyTorch Hub Model Checkpoints",
                    category=Category.AI_ML,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(torch_hub),
                    size_bytes=sz,
                    description="Downloaded vision/audio/NLP weights from torch.hub.",
                    cleanup_command=f'rm -rf "{torch_hub}"/*'
                ))

        # 3. Ollama Local LLMs
        ollama_models = home / ".ollama" / "models"
        if ollama_models.exists():
            sz = get_dir_size(ollama_models)
            if sz > 500 * 1024 * 1024:
                findings.append(Finding(
                    id="ollama_local_models",
                    title="Ollama Local LLM Model Blobs",
                    category=Category.AI_ML,
                    safety=SafetyLevel.REQUIRES_REVIEW,
                    path=str(ollama_models),
                    size_bytes=sz,
                    description="Locally pulled Ollama models (Llama, Mistral, Qwen, etc.).",
                    cleanup_command="ollama rm <model-name>  # or rm -rf ~/.ollama/models/*"
                ))

        # 4. TensorFlow Hub
        tf_hub = home / ".cache" / "tfhub_modules"
        if tf_hub.exists():
            sz = get_dir_size(tf_hub)
            if sz > 100 * 1024 * 1024:
                findings.append(Finding(
                    id="tensorflow_hub_modules",
                    title="TensorFlow Hub Cached Modules",
                    category=Category.AI_ML,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(tf_hub),
                    size_bytes=sz,
                    description="SavedModel artifacts downloaded from tfhub.dev.",
                    cleanup_command=f'rm -rf "{tf_hub}"/*'
                ))

        return findings
