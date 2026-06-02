"""Router backends — local (Ollama) i cloud (Anthropic)."""
from .local import LocalBackend
from .cloud import CloudBackend

__all__ = ["LocalBackend", "CloudBackend"]
