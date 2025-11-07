"""
MiniMax-M2 Provider Implementation (Local via Ollama)
Zero-cost local LLM provider for documentation generation
"""

import logging
import requests
from typing import Optional
from .base import LLMProvider, ProviderConfig

logger = logging.getLogger(__name__)


class MinimaxM2Provider(LLMProvider):
    """
    MiniMax-M2 provider running locally via Ollama

    Provides zero-cost documentation generation using the open-source
    MiniMax-M2 model (230B total params, 10B active MoE architecture).
    Optimized for coding and agentic workflows.
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        # Default configuration for MiniMax-M2 local
        if config is None:
            config = ProviderConfig(
                name="minimax-m2",
                model="minimax-m2:latest",
                max_tokens=16384,  # MiniMax-M2 supports long context
                temperature=0.0,
                # No rate limits for local execution
                requests_per_minute=None,
                requests_per_day=None,
                # Zero cost - running locally
                cost_per_1m_input=0.0,
                cost_per_1m_output=0.0
            )

        super().__init__(config)

        # Ollama API endpoint (default local)
        self.ollama_host = "http://localhost:11434"

        # Verify Ollama is running
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                available_models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in available_models]

                # Check if minimax-m2 is available
                if not any('minimax-m2' in name for name in model_names):
                    logger.warning(
                        "⚠️  MiniMax-M2 model not found in Ollama. "
                        "Run 'ollama pull minimax-m2:latest' to download the model."
                    )
                else:
                    logger.info("✅ MiniMax-M2 model available in Ollama")
            else:
                logger.warning(f"⚠️  Ollama responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.ollama_host}. "
                f"Make sure Ollama is running (run 'ollama serve' or check if service is active). "
                f"Error: {e}"
            )

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate documentation using MiniMax-M2 via Ollama

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context

        Returns:
            Generated documentation text
        """
        # Log first request info
        if self.request_count == 0:
            logger.info("🆓 Using MiniMax-M2 local (Ollama). No costs will be incurred!")
            logger.info(f"Model: {self.config.model} via {self.ollama_host}")

        # No rate limiting needed for local execution
        # But we still track request count
        self.request_count += 1

        try:
            # Build message payload for Ollama
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            logger.info(f"Sending request to Ollama ({self.config.model})")

            # Make API call to Ollama
            response = requests.post(
                f"{self.ollama_host}/api/chat",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    }
                },
                timeout=600  # 10 minute timeout for local inference
            )

            if response.status_code != 200:
                raise Exception(f"Ollama API error: Status {response.status_code}, Body: {response.text}")

            # Extract response
            result_data = response.json()
            result_text = result_data.get('message', {}).get('content', '')

            if not result_text:
                raise Exception(f"Empty response from Ollama: {result_data}")

            # Log stats (no cost tracking needed)
            logger.info(f"✅ Response received from Ollama (request #{self.request_count})")

            return result_text

        except requests.exceptions.Timeout:
            logger.error("⏱️ Ollama request timed out (10 minute limit)")
            raise Exception(
                "Ollama inference timed out. This may happen with very large prompts "
                "or if running on CPU without sufficient resources."
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama connection error: {e}")
            raise Exception(
                f"Failed to connect to Ollama. Make sure it's running: {e}"
            )
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def get_stats(self) -> dict:
        """Get provider statistics"""
        return {
            "provider": self.config.name,
            "model": self.config.model,
            "requests": self.request_count,
            "daily_requests": self.daily_request_count,
            "estimated_cost": "$0.00 (local execution)",
            "ollama_host": self.ollama_host
        }
