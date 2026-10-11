package warden

import future.keywords.in

default allow = false

# Restricted actions that can NEVER be performed by AI agents directly
restricted_actions := [
    "delete_database",
    "drop_table",
    "bulk_export_pii",
    "modify_iam_roles",
    "bypass_governance",
    "execute_arbitrary_code"
]

# Collect all policy violations
violations[msg] {
    input.agent.status != "active"
    msg := sprintf("Agent status is '%v', must be 'active'", [input.agent.status])
}

violations[msg] {
    input.action in restricted_actions
    msg := sprintf("Action '%v' is globally restricted for AI agents (requires human execution only)", [input.action])
}

violations[msg] {
    not input.action in input.agent.allowed_actions
    msg := sprintf("Action '%v' is not in agent allowed scope: %v", [input.action, input.agent.allowed_actions])
}

violations[msg] {
    not input.data_class in input.agent.allowed_data_classes
    msg := sprintf("Data classification '%v' exceeds agent allowed data classes: %v", [input.data_class, input.agent.allowed_data_classes])
}

violations[msg] {
    input.amount > input.agent.max_amount
    msg := sprintf("Requested amount %v exceeds agent maximum limit of %v", [input.amount, input.agent.max_amount])
}

# Allow only if there are zero violations
allow {
    count(violations) == 0
}
