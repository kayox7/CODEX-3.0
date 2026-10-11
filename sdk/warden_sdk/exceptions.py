"""WARDEN SDK Exceptions."""

class WardenError(Exception):
    """Base exception for all WARDEN SDK errors."""
    pass

class WardenBlocked(WardenError):
    """
    Raised when an action is blocked by policy, blast radius, human reviewer,
    or when governance evaluation fails (Fail-Closed principle).
    The guarded function is guaranteed to have NOT executed.
    """
    def __init__(self, message: str, decision_id: str = None, reason: str = None):
        super().__init__(message)
        self.decision_id = decision_id
        self.reason = reason

class WardenPolicyViolation(WardenBlocked):
    """Raised specifically when an action violates passport or OPA policies."""
    pass

class WardenApprovalTimeout(WardenBlocked):
    """Raised when an action awaiting human approval exceeds the polling SLA."""
    pass
