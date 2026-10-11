"""FastAPI endpoints for Connected AI Agents under /v1/connections.
Governs external AI provider models via WARDEN's pre-execution control pipeline.
"""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import get_current_user, require_roles
from app.providers.registry import list_provider_metadata
from app.schemas.connection import (
    ConnectionCreateRequest,
    ConnectionUpdateRequest,
    ConnectionRotateKeyRequest,
    ConnectionRunRequest,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectionRunResponse
)
from app.services import connection_service

router = APIRouter(prefix="", tags=["Connected AI Agents"])

@router.get("/v1/connections/providers")
@router.get("/connections/providers")
def get_provider_metadata_list(
    user: dict = Depends(require_roles(["admin", "auditor"]))
):
    """Return provider metadata array for UI registration form."""
    return list_provider_metadata()

@router.post("/v1/connections", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/connections", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection_endpoint(
    req: ConnectionCreateRequest,
    user: dict = Depends(require_roles(["admin"]))
):
    """Create a new external provider connection with encrypted key and backing passport."""
    return await connection_service.create_connection(req, created_by=user["username"])

@router.get("/v1/connections", response_model=List[ConnectionResponse])
@router.get("/connections", response_model=List[ConnectionResponse])
def list_connections_endpoint(
    user: dict = Depends(require_roles(["admin", "auditor"]))
):
    """List all registered external provider connections."""
    return connection_service.list_connections()

@router.get("/v1/connections/{connection_id}", response_model=ConnectionResponse)
@router.get("/connections/{connection_id}", response_model=ConnectionResponse)
def get_connection_endpoint(
    connection_id: str,
    user: dict = Depends(require_roles(["admin", "auditor"]))
):
    """Retrieve details for a single connection."""
    conn = connection_service.get_connection_by_id(connection_id)
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection '{connection_id}' not found"
        )
    return connection_service._to_public_response(conn)

@router.put("/v1/connections/{connection_id}", response_model=ConnectionResponse)
@router.put("/connections/{connection_id}", response_model=ConnectionResponse)
def update_connection_endpoint(
    connection_id: str,
    updates: ConnectionUpdateRequest,
    user: dict = Depends(require_roles(["admin"]))
):
    """Update connection attributes and synchronize backing passport."""
    return connection_service.update_connection(connection_id, updates, actor=user["username"])

@router.post("/v1/connections/{connection_id}/pause", response_model=ConnectionResponse)
@router.post("/connections/{connection_id}/pause", response_model=ConnectionResponse)
def pause_connection_endpoint(
    connection_id: str,
    user: dict = Depends(require_roles(["admin"]))
):
    """Pause connection and backing agent passport."""
    return connection_service.pause_connection(connection_id, actor=user["username"])

@router.post("/v1/connections/{connection_id}/resume", response_model=ConnectionResponse)
@router.post("/connections/{connection_id}/resume", response_model=ConnectionResponse)
def resume_connection_endpoint(
    connection_id: str,
    user: dict = Depends(require_roles(["admin"]))
):
    """Resume a paused connection."""
    return connection_service.resume_connection(connection_id, actor=user["username"])

@router.delete("/v1/connections/{connection_id}", response_model=ConnectionResponse)
@router.delete("/connections/{connection_id}", response_model=ConnectionResponse)
def revoke_connection_endpoint(
    connection_id: str,
    user: dict = Depends(require_roles(["admin"]))
):
    """Revoke and permanently disable an AI model connection."""
    return connection_service.revoke_connection(connection_id, actor=user["username"])

@router.post("/v1/connections/{connection_id}/rotate-key", response_model=ConnectionResponse)
@router.post("/connections/{connection_id}/rotate-key", response_model=ConnectionResponse)
async def rotate_key_endpoint(
    connection_id: str,
    req: ConnectionRotateKeyRequest,
    user: dict = Depends(require_roles(["admin"]))
):
    """Rotate provider API key. Old key is discarded; new key encrypted at rest."""
    return await connection_service.rotate_key(connection_id, req.api_key, actor=user["username"])

@router.post("/v1/connections/{connection_id}/test", response_model=ConnectionTestResponse)
@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection_endpoint(
    connection_id: str,
    user: dict = Depends(require_roles(["admin"]))
):
    """Run lightweight test call against upstream provider without leaking secrets."""
    return await connection_service.test_connection_endpoint(connection_id, actor=user["username"])

@router.post("/v1/connections/{connection_id}/run", response_model=ConnectionRunResponse)
@router.post("/connections/{connection_id}/run", response_model=ConnectionRunResponse)
async def run_connection_endpoint(
    connection_id: str,
    req: ConnectionRunRequest,
    user: dict = Depends(require_roles(["admin"]))
):
    """
    Run task with connected AI agent.
    Intercepts and governs every tool call proposed by the model through WARDEN pre-execution engine.
    """
    return await connection_service.run_connection_task(connection_id, req.task, actor=user["username"])
