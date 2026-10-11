import os
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file manually if exists
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

class Settings(BaseModel):
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    
    # Database
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./warden.db"))
    
    # Auth & JWT
    JWT_SECRET: str = Field(default_factory=lambda: os.getenv("JWT_SECRET", "warden_super_secret_demo_key_2026_change_in_prod"))
    JWT_ALGORITHM: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")))
    
    # Open Policy Agent
    OPA_URL: str = Field(default_factory=lambda: os.getenv("OPA_URL", "http://localhost:8181/v1/data/warden"))
    OPA_FALLBACK_ENABLED: bool = Field(default_factory=lambda: os.getenv("OPA_FALLBACK_ENABLED", "true").lower() in ("true", "1", "yes"))
    OPA_TIMEOUT_SECONDS: float = Field(default_factory=lambda: float(os.getenv("OPA_TIMEOUT_SECONDS", "2.0")))
    
    # Rego policy file path
    POLICIES_PATH: str = Field(default_factory=lambda: os.getenv("POLICIES_PATH", str(BASE_DIR / "policies" / "warden.rego")))
    
    # Approval SLAs & escalation interval (in seconds, default 120s for demo)
    APPROVAL_SLA_SECONDS: int = Field(default_factory=lambda: int(os.getenv("APPROVAL_SLA_SECONDS", os.getenv("DEFAULT_APPROVAL_SLA_SECONDS", "120"))))
    DEFAULT_APPROVAL_SLA_SECONDS: int = Field(default_factory=lambda: int(os.getenv("APPROVAL_SLA_SECONDS", os.getenv("DEFAULT_APPROVAL_SLA_SECONDS", "120"))))
    ESCALATION_CHECK_INTERVAL_SECONDS: int = Field(default_factory=lambda: int(os.getenv("ESCALATION_CHECK_INTERVAL_SECONDS", "5")))
    
    # Optional LLM keys
    GEMINI_API_KEY: str | None = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    ANTHROPIC_API_KEY: str | None = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))

    # Connected AI Agents Key Encryption & Security
    KEY_ENCRYPTION_SECRET: str | None = Field(default_factory=lambda: os.getenv("KEY_ENCRYPTION_SECRET"))
    ALLOW_LOCAL_UPSTREAMS: bool = Field(default_factory=lambda: os.getenv("ALLOW_LOCAL_UPSTREAMS", "false").lower() in ("true", "1", "yes"))

settings = Settings()
