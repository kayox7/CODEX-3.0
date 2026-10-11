import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON, Text
from app.database import Base

class ProviderType(str, enum.Enum):
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google_gemini"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    CUSTOM_OPENAI = "custom_openai"
    MOCK = "mock"

class ConnectionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"

class ProviderConnection(Base):
    __tablename__ = "provider_connections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    base_url = Column(String(500), nullable=False)
    model = Column(String(150), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    key_last4 = Column(String(10), nullable=False)
    agent_id = Column(String(100), nullable=False, index=True)
    system_prompt = Column(Text, nullable=True)
    allowed_actions = Column(JSON, nullable=False, default=list)
    allowed_data_classes = Column(JSON, nullable=False, default=list)
    max_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default=ConnectionStatus.ACTIVE.value)
    created_by = Column(String(100), nullable=False)
    created_at = Column(String(50), nullable=False)
    last_used_at = Column(String(50), nullable=True)
    last_test_status = Column(String(50), nullable=True)
    request_count = Column(Integer, nullable=False, default=0)
    blocked_count = Column(Integer, nullable=False, default=0)
