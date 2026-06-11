# -*- coding: utf-8 -*-
"""Read-only API for system credentials (API keys masked) and default model config."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentscope.app.deps import get_current_user_id, get_storage
from agentscope.app.storage import StorageBase

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


class DefaultModelResponse(BaseModel):
    type: str
    credential_id: str
    model: str


class SystemCredentialItem(BaseModel):
    id: str
    name: str
    data: dict


class SystemCredentialListResponse(BaseModel):
    credentials: list[SystemCredentialItem]
    total: int


@router.get("/system", response_model=SystemCredentialListResponse)
async def list_system_credentials(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> SystemCredentialListResponse:
    """Return the current user's system credentials with API keys masked."""
    from credential_loader import SYSTEM_CREDENTIAL_PREFIX, ensure_user_credentials

    # Ensure credentials exist for this user (handles new users created after startup)
    await ensure_user_credentials(storage, user_id)

    all_credentials = await storage.list_credentials(user_id)
    system_credentials = [
        c for c in all_credentials if c.id.startswith(SYSTEM_CREDENTIAL_PREFIX)
    ]

    masked: list[SystemCredentialItem] = []
    for cred in system_credentials:
        data = dict(cred.data)
        # Mask sensitive fields
        if "api_key" in data:
            data["api_key"] = "***"
        name = data.pop("name", "")
        masked.append(
            SystemCredentialItem(id=cred.id, name=name, data=data)
        )

    return SystemCredentialListResponse(
        credentials=masked,
        total=len(masked),
    )


@router.get("/default-model", response_model=DefaultModelResponse)
async def get_default_model(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> DefaultModelResponse:
    """Return the default model config from .env (LLM_PROVIDER + LLM_MODEL)."""
    from credential_loader import SYSTEM_CREDENTIAL_PREFIX, ensure_user_credentials

    await ensure_user_credentials(storage, user_id)

    model_name = os.getenv("LLM_MODEL", "")
    if not model_name:
        raise HTTPException(status_code=500, detail="LLM_MODEL not configured in .env")

    provider = os.getenv("LLM_PROVIDER", "").lower()

    all_credentials = await storage.list_credentials(user_id)
    system_credentials = [
        c for c in all_credentials if c.id.startswith(SYSTEM_CREDENTIAL_PREFIX)
    ]
    if not system_credentials:
        raise HTTPException(status_code=500, detail="No system credentials configured")

    # Match by LLM_PROVIDER env var (credential ID is system_{provider})
    cred = None
    if provider:
        target_id = f"{SYSTEM_CREDENTIAL_PREFIX}{provider}"
        cred = next((c for c in system_credentials if c.id == target_id), None)

    # Fallback to first system credential
    if cred is None:
        cred = system_credentials[0]

    return DefaultModelResponse(
        type=cred.data.get("type", ""),
        credential_id=cred.id,
        model=model_name,
    )
