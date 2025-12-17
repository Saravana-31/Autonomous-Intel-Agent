"""Offline LLM engine using Phi-2 via Hugging Face Transformers."""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Optional


class LLMEngine:
    """Local LLM engine for text generation using Phi-2."""
    
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
    
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.0
    ) -> str:
        """
        Generate text from prompt.
        
        Args:
            prompt: Input prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 for deterministic)
            
        Returns:
            Generated text
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
        
        # Decode only the new tokens
        generated = self.tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        )
        
        return generated.strip()
    
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._loaded


# Global singleton instance
_engine: Optional[LLMEngine] = None


def get_engine() -> LLMEngine:
    """Get or create the LLM engine singleton."""
    global _engine
    if _engine is None:
        _engine = LLMEngine()
    return _engine
