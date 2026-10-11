"""Agent Passport Registry endpoints.
Provides full CRUD, pause, resume, and kill switch operations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.agent import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentPassportResponse,
    AgentStatusActionRequest
)
from app.services import agent_service
from app.api.deps import get_current_user, require_roles

router = APIRouter(prefix="", tags=["Agents"])

@router.get("/agents", response_model=List[AgentPassportResponse])
@router.get("/v1/agents", response_model=List[AgentPassportResponse])
def list_agents(user: dict = Depends(get_current_user)):
    """List all registered agent passports."""
    return agent_service.get_all_agents()

@router.get("/agents/{agent_id}", response_model=AgentPassportResponse)
@router.get("/v1/agents/{agent_id}", response_model=AgentPassportResponse)
def get_agent(agent_id: str, user: dict = Depends(get_current_user)):
    """Get single agent passport by agent_id."""
    agent = agent_service.get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")
    return agent

@router.post("/agents", response_model=AgentPassportResponse, status_code=status.HTTP_201_CREATED)
@router.post("/v1/agents", response_model=AgentPassportResponse, status_code=status.HTTP_201_CREATED)
def register_agent(
    req: AgentCreateRequest,
    user: dict = Depends(require_roles(["admin", "risk_lead"]))
):
    """Register a new agent passport with scope limits, budget caps, and API key."""
    existing = agent_service.get_agent_by_id(req.agent_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Agent '{req.agent_id}' already exists")

    return agent_service.create_agent(
        agent_id=req.agent_id,
        name=req.name,
        owner=req.owner or user["username"],
        purpose=req.purpose,
        allowed_actions=req.allowed_actions,
        allowed_data_classes=req.allowed_data_classes,
        max_amount=req.max_amount,
        status=req.status,
        custom_api_key=req.custom_api_key
    )

@router.put("/agents/{agent_id}", response_model=AgentPassportResponse)
@router.put("/v1/agents/{agent_id}", response_model=AgentPassportResponse)
def update_agent_passport(
    agent_id: str,
    req: AgentUpdateRequest,
    user: dict = Depends(require_roles(["admin", "risk_lead"]))
):
    """Update agent passport constraints or metadata."""
    updates = req.model_dump(exclude_unset=True)
    updated = agent_service.update_agent(agent_id, updates, actor=user["username"])
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")
    return updated

@router.post("/agents/{agent_id}/pause")
@router.post("/v1/agents/{agent_id}/pause")
def pause_agent_endpoint(
    agent_id: str,
    req: Optional[AgentStatusActionRequest] = None,
    user: dict = Depends(require_roles(["admin", "approver", "risk_lead", "executive"]))
):
    """
    Emergency Kill Switch: Pause agent execution.
    Denies all subsequent pre-execution action requests immediately.
    """
    reason = req.reason if req and req.reason else f"Paused manually by {user['username']}"
    try:
        return agent_service.pause_agent(agent_id, reason=reason, actor=user["username"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/agents/{agent_id}/resume")
@router.post("/v1/agents/{agent_id}/resume")
def resume_agent_endpoint(
    agent_id: str,
    req: Optional[AgentStatusActionRequest] = None,
    user: dict = Depends(require_roles(["admin", "risk_lead", "executive"]))
):
    """Resume a paused agent passport, re-enabling governed execution."""
    reason = req.reason if req and req.reason else f"Resumed manually by {user['username']}"
    try:
        return agent_service.resume_agent(agent_id, reason=reason, actor=user["username"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
