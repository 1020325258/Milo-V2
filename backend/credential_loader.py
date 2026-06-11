# -*- coding: utf-8 -*-
"""Load LLM API keys from environment variables and create system credentials for users."""
import logging
import os
from typing import Type

from agentscope.credential import (
    AnthropicCredential,
    CredentialBase,
    DashScopeCredential,
    DeepSeekCredential,
    GeminiCredential,
    MoonshotCredential,
    OllamaCredential,
    OpenAICredential,
    XAICredential,
)
from agentscope.app.storage import StorageBase

logger = logging.getLogger(__name__)

# Deterministic ID prefix for system credentials
SYSTEM_CREDENTIAL_PREFIX = "system_"

# (CredentialClass, env_prefix)
PROVIDER_CONFIGS: list[tuple[Type[CredentialBase], str]] = [
    (OpenAICredential, "OPENAI"),
    (AnthropicCredential, "ANTHROPIC"),
    (DashScopeCredential, "DASHSCOPE"),
    (DeepSeekCredential, "DEEPSEEK"),
    (GeminiCredential, "GEMINI"),
    (MoonshotCredential, "MOONSHOT"),
    (OllamaCredential, "OLLAMA"),
    (XAICredential, "XAI"),
]


def _build_credential_from_env(
    cls: Type[CredentialBase],
    prefix: str,
) -> CredentialBase | None:
    """Build a credential instance from environment variables.

    Returns None if the required API key is not set.
    """
    # Ollama doesn't need an API key, only host
    if cls is OllamaCredential:
        host = os.getenv(f"{prefix}_HOST")
        if host is None:
            return None
        return cls(host=host)

    api_key = os.getenv(f"{prefix}_API_KEY")
    if not api_key:
        return None

    kwargs: dict = {"api_key": api_key}

    base_url = os.getenv(f"{prefix}_BASE_URL")
    if base_url and "base_url" in cls.model_fields:
        kwargs["base_url"] = base_url

    if cls is OpenAICredential:
        org = os.getenv(f"{prefix}_ORGANIZATION")
        if org:
            kwargs["organization"] = org

    if cls is XAICredential:
        host = os.getenv(f"{prefix}_API_HOST")
        if host:
            kwargs["api_host"] = host

    try:
        return cls(**kwargs)
    except Exception as e:
        logger.warning("Failed to create %s credential from env: %s", cls.__name__, e)
        return None


async def ensure_user_credentials(
    storage: StorageBase,
    user_id: str,
) -> None:
    """Create system credentials for a user if they don't exist yet.

    Idempotent: uses deterministic credential IDs (system_{prefix}).
    """
    existing = await storage.list_credentials(user_id)
    existing_ids = {c.id for c in existing}

    for cls, prefix in PROVIDER_CONFIGS:
        credential_id = f"{SYSTEM_CREDENTIAL_PREFIX}{prefix.lower()}"
        if credential_id in existing_ids:
            continue

        credential = _build_credential_from_env(cls, prefix)
        if credential is None:
            continue

        credential.id = credential_id
        credential.name = f"System {cls.model_config.get('title', prefix)}"
        await storage.upsert_credential(user_id, credential)
        logger.info("Created system credential %s for user %s", prefix, user_id)


async def ensure_all_existing_users(storage: StorageBase) -> None:
    """Scan Redis for all existing users and create system credentials for each."""
    client = storage.get_client()
    cursor = 0
    user_ids: set[str] = set()

    # Scan for all credential index keys to find existing users
    while True:
        cursor, keys = await client.scan(
            cursor,
            match="agentscope:user:*:credentials",
            count=100,
        )
        for key in keys:
            # Extract user_id from key: agentscope:user:{user_id}:credentials
            parts = key.split(":")
            if len(parts) >= 4:
                user_ids.add(parts[2])
        if cursor == 0:
            break

    if not user_ids:
        logger.info("No existing users found in Redis")
        return

    logger.info("Found %d existing user(s), creating system credentials...", len(user_ids))
    for user_id in user_ids:
        await ensure_user_credentials(storage, user_id)

    logger.info("System credentials created for all existing users")
