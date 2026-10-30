"""Mask personal data in Turkish text before it reaches an LLM, and restore it afterwards."""

from .detect import Kind, Span, detect
from .validators import is_valid_tckn, is_valid_tr_iban, is_valid_vkn
from .vault import Vault

__all__ = ["Kind", "Span", "Vault", "detect", "is_valid_tckn", "is_valid_tr_iban", "is_valid_vkn"]
__version__ = "0.1.0"
