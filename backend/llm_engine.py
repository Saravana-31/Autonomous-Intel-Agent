"""Offline LLM engine using Phi-2 via Hugging Face Transformers.

This file now exposes a provider manager via `get_engine()` that returns
an object compatible with the previous `LLMEngine` (has `generate`,
`load_model`, `is_loaded`).

Phi-2 implementation (original) is preserved and wrapped by `Phi2Provider`.
An `OllamaProvider` is added as the primary provider with automatic
fallback to Phi-2.
"""

import os
import time
import json
from typing import Optional, Dict, Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import requests


class LLMEngine:
    """Local LLM engine for text generation using Phi-2.

    ORIGINAL implementation preserved. Do not change behavior.
    """
    MODEL_NAME = "microsoft/phi-2"

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        self._loaded = False

    def load_model(self) -> None:
        """Load the Phi-2 model and tokenizer."""
        if self._loaded:
            return

        print(f"Loading model: {self.MODEL_NAME}")
        print("This may take a few minutes on first run...")

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_NAME,
            trust_remote_code=True
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            self.MODEL_NAME,
            torch_dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

        self.model.eval()
        self._loaded = True
        print("Model loaded successfully!")

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.0) -> str:
        """Generate text from prompt.

        Behavior unchanged from original implementation.
        """
        if not self._loaded:
            self.load_model()

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1024
        )

        with torch.no_grad():
            outputs = self.model.generate(
                inputs.input_ids,
                attention_mask=inputs.attention_mask,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                num_beams=1,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )

        generated = self.tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        )

        return generated.strip()

    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._loaded


# --- Provider abstractions and implementations ---


class BaseLLMProvider:
    """Base interface for LLM providers."""

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.0) -> str:
        raise NotImplementedError()

    def load_model(self) -> None:
        """Optional: prepare provider for use (load local model or run health checks)."""
        pass

    def is_loaded(self) -> bool:
        return False


class Phi2Provider(BaseLLMProvider):
    """Provider wrapper around the existing local Phi-2 `LLMEngine`.

    This wrapper delegates to the original `LLMEngine` so the offline
    behavior and performance characteristics remain unchanged.
    """

    def __init__(self, engine: Optional[LLMEngine] = None):
        self._engine = engine or LLMEngine()

    def load_model(self) -> None:
        self._engine.load_model()

    def is_loaded(self) -> bool:
        return self._engine.is_loaded()

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.0) -> str:
        return self._engine.generate(prompt, max_new_tokens=max_new_tokens, temperature=temperature)


class OllamaProvider(BaseLLMProvider):
    """Ollama (OpenAI-compatible) provider.

    Posts to the configured OLLAMA API endpoint using the chat completions
    API. Deterministic settings (temperature=0) are enforced and timeouts
    are limited to 30s.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3")
        self.timeout = 30

    def _endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/v1/chat/completions"

    def _health_endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/v1/models"

    def load_model(self) -> None:
        # No local model to load; perform a quick health check.
        try:
            resp = requests.get(self._health_endpoint(), timeout=5)
            if resp.status_code == 200:
                print("LLM Provider: Ollama")
            else:
                print("LLM Provider: Ollama (unhealthy response)")
        except Exception:
            print("LLM Provider: Ollama (unreachable)")

    def is_loaded(self) -> bool:
        # Ollama is networked — return True only if reachable
        try:
            resp = requests.get(self._health_endpoint(), timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.0) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(0.0),
            "max_tokens": int(max_new_tokens)
        }

        try:
            resp = requests.post(self._endpoint(), json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # OpenAI-compatible chat response parsing
            choices = data.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                return message.get("content", "").strip()

            # Fallback: try text field
            return data.get("text", "").strip()

        except Exception as e:
            # Bubble up exception to let manager trigger fallback
            raise


class ProviderManager(BaseLLMProvider):
    """Manager that selects Ollama as primary and falls back to Phi-2.

    Provides the same surface as the original `LLMEngine` so existing
    code (`extractor`, `main`) continues to work unchanged.
    """

    def __init__(self):
        self.ollama = OllamaProvider()
        self.phi2 = Phi2Provider()
        self._primary_available = None

    def _ensure_primary(self) -> bool:
        if self._primary_available is not None:
            return self._primary_available

        try:
            ok = self.ollama.is_loaded()
            if ok:
                print("LLM Provider: Ollama")
            else:
                print("Offline mode detected — using Phi-2" if not self._network_available() else "Ollama unreachable — using Phi-2")
            self._primary_available = ok
            return ok
        except Exception:
            self._primary_available = False
            return False

    def _network_available(self) -> bool:
        # quick probe to determine if system is offline
        try:
            requests.get("https://1.1.1.1", timeout=2)
            return True
        except Exception:
            return False

    def load_model(self) -> None:
        # On startup, check Ollama and only load Phi-2 if needed.
        primary_ok = self._ensure_primary()
        if not primary_ok:
            print("Ollama failed — falling back to Phi-2")
            self.phi2.load_model()

    def is_loaded(self) -> bool:
        # Report primary health if available, otherwise local engine state
        if self._ensure_primary():
            return True
        return self.phi2.is_loaded()

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.0) -> str:
        # Wrap prompt with deterministic anti-hallucination snippet for Ollama
        mandatory_fields = (
            "Mandatory fields to extract if present: company_information, company_name, domain, description, "
            "industry, sub_industry, products_offered, services_offered, contact_information, email_addresses, "
            "phone_numbers, physical_address, city, country, services, people_information, person_name, role, "
            "associated_company, social_media (platform + url), certifications (certification_name + issuing_authority)."
        )

        ollama_prompt = (
            "Extract information ONLY from the provided text. "
            "If a field is not present, return null or an empty list. "
            "Do NOT assume or invent information. "
            "Return JSON-friendly output. "
            + mandatory_fields
            + "\n\n"
            + prompt
        )

        start = time.time()

        # Try Ollama first
        try:
            if self._ensure_primary():
                resp = self.ollama.generate(ollama_prompt, max_new_tokens=max_new_tokens, temperature=0.0)
                duration = time.time() - start
                print(f"Extraction via Ollama took {duration:.2f}s")
                return resp
        except Exception:
            print("Ollama failed — falling back to Phi-2")

        # Fallback to local Phi-2
        try:
            resp = self.phi2.generate(prompt, max_new_tokens=max_new_tokens, temperature=temperature)
            duration = time.time() - start
            print(f"Extraction via Phi-2 took {duration:.2f}s")
            return resp
        except Exception:
            # Last-resort: never crash, return empty JSON
            print("Both Ollama and Phi-2 failed to generate a response")
            return "{}"

    def health(self) -> Dict[str, Any]:
        """Return health information about providers."""
        primary_ok = self._ensure_primary()
        return {
            "primary": "Ollama",
            "primary_ok": bool(primary_ok),
            "fallback": "Phi-2",
            "fallback_loaded": bool(self.phi2.is_loaded()),
        }


# Global provider singleton
_provider: Optional[ProviderManager] = None


def get_engine() -> ProviderManager:
    """Return the provider manager used by the application.

    This preserves the public surface used by the rest of the codebase.
    """
    global _provider
    if _provider is None:
        _provider = ProviderManager()
    return _provider

