# sentinel/core/prompt_guard.py
"""
Camada dedicada de detecção de prompt injection/jailbreak, via Llama
Prompt Guard 2 (86M). Não usar Ollama aqui: é um classificador de texto
(mDeBERTa), não um LLM generativo GGUF.

Requer aceitar a licença em https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M
e configurar HF_TOKEN no ambiente antes do primeiro download.
"""
import logging
from functools import lru_cache

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)

_MODEL_ID = "meta-llama/Llama-Prompt-Guard-2-86M"
_MODEL_REVISION = "a8ded8e697ce7c355e395a0df51f94adb4a2fd27"
_MALICIOUS_CLASS_ID = 1


@lru_cache(maxsize=1)
def _load_prompt_guard():
    """Carrega uma única vez por processo — ~350MB, tranquilo em CPU ou GPU."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID, revision=_MODEL_REVISION)
    model = AutoModelForSequenceClassification.from_pretrained(
        _MODEL_ID,
        revision=_MODEL_REVISION,
    ).to(device)
    model.eval()
    logger.info("Prompt Guard 2 carregado em %s.", device)
    return tokenizer, model, device


def check_prompt_injection(text: str) -> bool:
    """True se o texto for classificado como malicioso (injeção/jailbreak)."""
    try:
        tokenizer, model, device = _load_prompt_guard()
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
        predicted_id = logits.argmax().item()

        if predicted_id == _MALICIOUS_CLASS_ID:
            logger.warning("Prompt Guard 2: ataque detectado — texto: %.80s...", text)
            return True
        return False
    except (OSError, RuntimeError, ValueError):
        logger.exception("Prompt Guard 2: falha na inferência. Bloqueio defensivo (fail-safe).")
        return True