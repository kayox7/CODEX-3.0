"""Cryptographic utilities for Provider Connection key encryption at rest.
Uses Fernet symmetric encryption with key from KEY_ENCRYPTION_SECRET.
Strict fail-closed: refuses to encrypt or decrypt without a valid Fernet key.
"""
import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from app.config import settings

SECRET_GENERATION_INSTRUCTION = (
    "KEY_ENCRYPTION_SECRET is missing or invalid. "
    "Please generate a valid Fernet key using: "
    'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" '
    "and configure it in your environment."
)

class EncryptionConfigError(Exception):
    """Raised when KEY_ENCRYPTION_SECRET is missing or invalid."""
    pass

def get_fernet() -> Fernet:
    """Instantiate Fernet cipher from environment configuration."""
    secret = settings.KEY_ENCRYPTION_SECRET or os.getenv("KEY_ENCRYPTION_SECRET")
    if not secret:
        raise EncryptionConfigError(SECRET_GENERATION_INSTRUCTION)
    
    secret_bytes = secret.strip().encode("utf-8")
    try:
        return Fernet(secret_bytes)
    except Exception as exc:
        raise EncryptionConfigError(f"Invalid KEY_ENCRYPTION_SECRET: {exc}. {SECRET_GENERATION_INSTRUCTION}") from exc

def encrypt_key(raw_key: str) -> str:
    """Encrypt raw provider API key at rest."""
    if not raw_key or not raw_key.strip():
        raise ValueError("Cannot encrypt an empty API key")
    
    try:
        fernet = get_fernet()
        encrypted_bytes = fernet.encrypt(raw_key.strip().encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    except EncryptionConfigError:
        raise
    except Exception as exc:
        raise EncryptionConfigError(f"Encryption failed: {exc}") from exc

def decrypt_key(encrypted_key: str) -> str:
    """Decrypt encrypted provider API key for server-side provider call."""
    if not encrypted_key:
        raise ValueError("Cannot decrypt empty encrypted key")
    
    try:
        fernet = get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_key.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except EncryptionConfigError:
        raise
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt API key: Invalid encryption token or altered secret.") from exc
    except Exception as exc:
        raise ValueError(f"Failed to decrypt API key: {exc}") from exc

def extract_key_last4(raw_key: str) -> str:
    """Extract safe last 4 characters of key without leaking secrets."""
    if not raw_key:
        return "****"
    cleaned = raw_key.strip()
    if len(cleaned) <= 4:
        return cleaned
    return cleaned[-4:]

def mask_key(raw_key: str) -> str:
    """Safely mask key for display or logging (e.g. '...4a2b')."""
    last4 = extract_key_last4(raw_key)
    return f"...{last4}"
