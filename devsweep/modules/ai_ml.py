"""
devsweep.modules.ai_ml
======================

Scanner for local AI / Machine Learning framework caches and model weights.

What is inspected
-----------------
* **Hugging Face Hub** (``~/.cache/huggingface/hub``) — pre-trained transformers,
  LLMs, and embedding models downloaded via the ``huggingface_hub`` library or
  ``from_pretrained()``.
* **PyTorch Hub** (``~/.cache/torch/hub``) — vision, audio, and NLP weights
  fetched via ``torch.hub.load()``.
* **Ollama** (``~/.ollama/models``) — locally pulled LLM blobs for models like
  Llama, Mistral, and Qwen.  Marked REQUIRES_REVIEW because models cannot be
  automatically re-downloaded; the user must explicitly re-pull.
* **TensorFlow Hub** (``~/.cache/tfhub_modules``) — SavedModel artefacts from
  ``tfhub.dev``.

All of these caches are safe to delete (SAFE_CACHE), **except Ollama models**
which are REQUIRES_REVIEW because re-downloading them takes significant time
and bandwidth.

Size thresholds
---------------
Model weight files are typically very large (100 MB–several GB).  We use a
100 MB minimum threshold for framework caches and 500 MB for Ollama to avoid
reporting empty or near-empty stores.

To add a new AI/ML cache
-------------------------
1. Identify the cache directory (usually ``~/.cache/<framework>``).
2. Add a block following the same pattern as the examples below.
3. Choose ``SAFE_CACHE`` if the framework can re-download automatically, or
   ``REQUIRES_REVIEW`` if the user must manually re-pull/re-train.
"""

from pathlib import Path
from typing import List

from devsweep.core.models import Category, Finding, SafetyLevel
from devsweep.core.scanner import BaseScanner
from devsweep.core.utils import get_dir_size, get_home_dir


class AIMLScanner(BaseScanner):
    """Scanner for AI/ML framework model caches.

    Checks standard cache locations for HuggingFace Hub, PyTorch Hub, Ollama,
    and TensorFlow Hub.  Returns a ``Finding`` for each cache that exceeds the
    relevant size threshold.
    """

    @property
    def name(self) -> str:
        return "ai_ml"

    @property
    def description(self) -> str:
        return "Scans HuggingFace, PyTorch Hub, Ollama, and local AI model weights"

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        home = get_home_dir()

        # ------------------------------------------------------------------
        # 1. Hugging Face Hub model cache
        #    ~/.cache/huggingface/hub  (macOS/Linux)
        #
        #    Contains blobs, snapshots, and refs for every model version ever
        #    downloaded via `from_pretrained()` or `hf_hub_download()`.
        #    The `huggingface-cli delete-cache` interactive TUI lets users pick
        #    individual model revisions to delete instead of nuking everything.
        # ------------------------------------------------------------------
        hf_hub = home / ".cache" / "huggingface" / "hub"
        if hf_hub.exists():
            sz = get_dir_size(hf_hub)
            if sz > 100 * 1024 * 1024:  # report only when > 100 MB
                findings.append(Finding(
                    id="huggingface_hub_models",
                    title="Hugging Face Cached Model Weights",
                    category=Category.AI_ML,
                    safety=SafetyLevel.SAFE_CACHE,
                    path=str(hf_hub),
                    size_bytes=sz,
                    description=(
                        "Pre-trained transformers, LLMs, and embedding weights "
                        "downloaded via HuggingFace Hub."
                    ),
                    cleanup_command=(
                        f'rm -rf "{hf_hub}"/*  '
                        "# or use: huggingface-cli delete-cache"
                    ),
                ))

        # ------------------------------------------------------------------
        # 2. PyTorch Hub model checkpoints
        #    ~/.cache/torch/hub
        #
        #    Populated by `torch.hub.load()` calls.  Removing the cache folder
        #    causes PyTorch to re-download on the next `hub.load()` call.
        # ------------------------------------------------------------------
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
                    description=(
                        "Downloaded vision/audio/NLP weights from torch.hub."
                    ),
                    cleanup_command=f'rm -rf "{torch_hub}"/*',
                ))

        # ------------------------------------------------------------------
        # 3. Ollama local LLM model blobs
        #    ~/.ollama/models
        #
        #    Each `ollama pull <model>` downloads multi-GB GGUF / GGML files
        #    here.  Unlike the framework caches above, Ollama does NOT
        #    re-pull automatically — the user must run `ollama pull <model>`
        #    again.  Therefore this is REQUIRES_REVIEW.
        # ------------------------------------------------------------------
        ollama_models = home / ".ollama" / "models"
        if ollama_models.exists():
            sz = get_dir_size(ollama_models)
            if sz > 500 * 1024 * 1024:  # higher threshold — models are huge
                findings.append(Finding(
                    id="ollama_local_models",
                    title="Ollama Local LLM Model Blobs",
                    category=Category.AI_ML,
                    safety=SafetyLevel.REQUIRES_REVIEW,
                    path=str(ollama_models),
                    size_bytes=sz,
                    description=(
                        "Locally pulled Ollama models (Llama, Mistral, Qwen, etc.). "
                        "Use `ollama list` to see which models are installed."
                    ),
                    cleanup_command=(
                        "ollama rm <model-name>  "
                        "# or: rm -rf ~/.ollama/models/*"
                    ),
                ))

        # ------------------------------------------------------------------
        # 4. TensorFlow Hub cached modules
        #    ~/.cache/tfhub_modules
        #
        #    SavedModel bundles from `tensorflow_hub.load()`.  Removed modules
        #    are transparently re-downloaded on the next TF Hub load call.
        # ------------------------------------------------------------------
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
                    description=(
                        "SavedModel artefacts downloaded from tfhub.dev."
                    ),
                    cleanup_command=f'rm -rf "{tf_hub}"/*',
                ))

        return findings
