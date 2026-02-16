from .llm_openai import get_openai_like_provider
from .llm_ollama import get_ollama_provider
from .llm_gemini import get_gemini_provider
from .llm_mock import get_mock_provider
from ..core.config import settings
from .llm_base import LLMProvider


# Global provider instance for lazy loading
_provider_instance = None

def get_provider() -> LLMProvider:
	global _provider_instance
	if _provider_instance is not None:
		return _provider_instance
		
	provider = (settings.LLM_PROVIDER or "").lower()
	print(f"🔍 LLM Provider setting: '{settings.LLM_PROVIDER}' -> '{provider}'")
	
	if provider in ("openai", "openrouter"):
		_provider_instance = get_openai_like_provider()
		print("🔍 Using OpenAI provider")
	elif provider == "ollama":
		_provider_instance = get_ollama_provider()
		print("🔍 Using Ollama provider")
	elif provider == "gemini":
		_provider_instance = get_gemini_provider(settings.GEMINI_API_KEY)
		print("🔍 Using Gemini provider")
	elif provider == "mock":
		_provider_instance = get_mock_provider()
		print("🔍 Using Mock provider")
	else:
		# Default to mock provider for reliability
		_provider_instance = get_mock_provider()
		print(f"🔍 Using Mock provider (default, unknown provider: '{provider}')")
	
	return _provider_instance