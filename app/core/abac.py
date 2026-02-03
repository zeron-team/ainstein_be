# app/core/abac.py
"""
FERRO D2 v3.0.0 - ABAC (Attribute-Based Access Control) Evaluator

Provides deterministic authorization decisions with full audit trail.

FERRO D2 ABAC Contract:
- Policies are JSON with versioned rules
- Strategy: deny_overrides (any deny wins)
- Default: deny (explicit allow required)
- All decisions logged with matched_rules + trace_id
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class ABACSubject:
    """Subject (who) in ABAC decision."""
    user_id: str
    tenant_id: str
    roles: List[str]
    attributes: Dict[str, Any] = None
    
    def __post_init__(self):
        self.attributes = self.attributes or {}


@dataclass
class ABACResource:
    """Resource (what) in ABAC decision."""
    type: str
    id: Optional[str] = None
    tenant_id: Optional[str] = None
    owner_id: Optional[str] = None
    attributes: Dict[str, Any] = None
    
    def __post_init__(self):
        self.attributes = self.attributes or {}


@dataclass
class ABACContext:
    """Context (environment) for ABAC decision."""
    trace_id: str
    action: str
    timestamp: datetime = None
    ip_address: Optional[str] = None
    attributes: Dict[str, Any] = None
    
    def __post_init__(self):
        self.timestamp = self.timestamp or datetime.utcnow()
        self.attributes = self.attributes or {}


@dataclass
class ABACDecision:
    """Result of ABAC evaluation."""
    effect: str  # "allow" or "deny"
    matched_rules: List[str]
    policy_version: int
    trace_id: str
    
    @property
    def allowed(self) -> bool:
        return self.effect == "allow"


class ABACEvaluator:
    """
    FERRO D2 ABAC Policy Evaluator.
    
    Policy Structure:
    {
        "version": 3,
        "strategy": "deny_overrides",
        "default": "deny",
        "rules": [
            {
                "id": "R1",
                "effect": "allow",
                "actions": ["doc.read"],
                "resource": {"type": "document"},
                "when": {
                    "all": [
                        {"eq": ["subject.tenant_id", "resource.tenant_id"]},
                        {"in": ["subject.roles", ["admin", "user"]]}
                    ]
                },
                "priority": 100
            }
        ]
    }
    """
    
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self.version = policy.get("version", 1)
        self.strategy = policy.get("strategy", "deny_overrides")
        self.default = policy.get("default", "deny")
        self.rules = sorted(
            policy.get("rules", []),
            key=lambda r: (-r.get("priority", 0), r.get("id", ""))
        )
    
    def evaluate(
        self,
        subject: ABACSubject,
        resource: ABACResource,
        context: ABACContext,
    ) -> ABACDecision:
        """
        Evaluate policy against subject, resource, and context.
        
        Strategy: deny_overrides
        - If any rule returns DENY, final decision is DENY
        - If at least one rule returns ALLOW and no DENY, final is ALLOW
        - If no rules match, use default (deny)
        """
        matched_allows: List[str] = []
        matched_denies: List[str] = []
        
        # Build evaluation context
        eval_ctx = self._build_eval_context(subject, resource, context)
        
        for rule in self.rules:
            if self._rule_matches(rule, eval_ctx):
                rule_id = rule.get("id", "unknown")
                effect = rule.get("effect", "deny")
                
                if effect == "deny":
                    matched_denies.append(rule_id)
                elif effect == "allow":
                    matched_allows.append(rule_id)
                
                log.debug("[ABAC] Rule %s matched with effect=%s", rule_id, effect)
        
        # Apply strategy
        if self.strategy == "deny_overrides":
            if matched_denies:
                effect = "deny"
                matched = matched_denies
            elif matched_allows:
                effect = "allow"
                matched = matched_allows
            else:
                effect = self.default
                matched = []
        else:
            # Default to deny_overrides
            effect = "deny" if matched_denies else ("allow" if matched_allows else self.default)
            matched = matched_denies or matched_allows or []
        
        decision = ABACDecision(
            effect=effect,
            matched_rules=matched,
            policy_version=self.version,
            trace_id=context.trace_id,
        )
        
        log.info(
            "[ABAC] Decision: %s | action=%s | resource=%s | rules=%s | trace=%s",
            effect.upper(),
            context.action,
            resource.type,
            matched,
            context.trace_id,
        )
        
        return decision
    
    def _build_eval_context(
        self,
        subject: ABACSubject,
        resource: ABACResource,
        context: ABACContext,
    ) -> Dict[str, Any]:
        """Build flat evaluation context for condition matching."""
        return {
            "subject.user_id": subject.user_id,
            "subject.tenant_id": subject.tenant_id,
            "subject.roles": subject.roles,
            **{f"subject.{k}": v for k, v in subject.attributes.items()},
            
            "resource.type": resource.type,
            "resource.id": resource.id,
            "resource.tenant_id": resource.tenant_id,
            "resource.owner_id": resource.owner_id,
            **{f"resource.{k}": v for k, v in resource.attributes.items()},
            
            "context.action": context.action,
            "context.timestamp": context.timestamp.isoformat() if context.timestamp else None,
            "context.ip_address": context.ip_address,
            **{f"context.{k}": v for k, v in context.attributes.items()},
        }
    
    def _rule_matches(self, rule: Dict[str, Any], eval_ctx: Dict[str, Any]) -> bool:
        """Check if a rule matches the current evaluation context."""
        # Check action match
        actions = rule.get("actions", [])
        current_action = eval_ctx.get("context.action", "")
        if actions and current_action not in actions and "*" not in actions:
            return False
        
        # Check resource type match
        resource_spec = rule.get("resource", {})
        if resource_spec:
            required_type = resource_spec.get("type")
            if required_type and required_type != eval_ctx.get("resource.type"):
                return False
        
        # Check conditions
        when = rule.get("when")
        if when:
            return self._evaluate_condition(when, eval_ctx)
        
        return True
    
    def _evaluate_condition(self, condition: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
        """Evaluate a condition expression."""
        if "all" in condition:
            return all(self._evaluate_condition(c, ctx) for c in condition["all"])
        
        if "any" in condition:
            return any(self._evaluate_condition(c, ctx) for c in condition["any"])
        
        if "not" in condition:
            return not self._evaluate_condition(condition["not"], ctx)
        
        if "eq" in condition:
            left, right = condition["eq"]
            left_val = self._resolve_value(left, ctx)
            right_val = self._resolve_value(right, ctx)
            return left_val == right_val
        
        if "in" in condition:
            value_ref, collection_ref = condition["in"]
            value = self._resolve_value(value_ref, ctx)
            collection = self._resolve_value(collection_ref, ctx)
            if isinstance(value, list):
                return any(v in collection for v in value)
            return value in collection
        
        if "contains" in condition:
            collection_ref, value_ref = condition["contains"]
            collection = self._resolve_value(collection_ref, ctx)
            value = self._resolve_value(value_ref, ctx)
            return value in collection if collection else False
        
        return False
    
    def _resolve_value(self, ref: Any, ctx: Dict[str, Any]) -> Any:
        """Resolve a value reference (either literal or context path)."""
        if isinstance(ref, str) and "." in ref:
            return ctx.get(ref)
        return ref


# ============================================================================
# Default Policies
# ============================================================================

DEFAULT_TENANT_POLICY = {
    "version": 3,
    "strategy": "deny_overrides",
    "default": "deny",
    "rules": [
        {
            "id": "R1_TENANT_ISOLATION",
            "effect": "allow",
            "actions": ["*"],
            "resource": {"type": "*"},
            "when": {
                "eq": ["subject.tenant_id", "resource.tenant_id"]
            },
            "priority": 100,
            "description": "Allow access to resources in same tenant"
        },
        {
            "id": "R2_OWNER_ACCESS",
            "effect": "allow",
            "actions": ["*"],
            "resource": {"type": "*"},
            "when": {
                "eq": ["subject.user_id", "resource.owner_id"]
            },
            "priority": 90,
            "description": "Allow owners full access to their resources"
        },
        {
            "id": "R3_ADMIN_ACCESS",
            "effect": "allow",
            "actions": ["*"],
            "resource": {"type": "*"},
            "when": {
                "all": [
                    {"eq": ["subject.tenant_id", "resource.tenant_id"]},
                    {"in": ["subject.roles", ["admin", "superadmin"]]}
                ]
            },
            "priority": 80,
            "description": "Allow admins full access within tenant"
        }
    ]
}


def get_default_evaluator() -> ABACEvaluator:
    """Get evaluator with default tenant isolation policy."""
    return ABACEvaluator(DEFAULT_TENANT_POLICY)


async def log_abac_decision(
    db,
    decision: ABACDecision,
    subject: ABACSubject,
    resource: ABACResource,
    context: ABACContext,
) -> None:
    """
    Log ABAC decision to audit table.
    
    FERRO D2 Requirement: All decisions must be audited with matched_rules + trace_id
    """
    try:
        from sqlalchemy import text
        
        await db.execute(
            text("""
                INSERT INTO abac_audit_log 
                (trace_id, tenant_id, user_id, action, resource_type, resource_id, 
                 effect, matched_rules, policy_version, context)
                VALUES (:trace_id, :tenant_id, :user_id, :action, :resource_type, 
                        :resource_id, :effect, :matched_rules, :policy_version, :context)
            """),
            {
                "trace_id": decision.trace_id,
                "tenant_id": subject.tenant_id,
                "user_id": subject.user_id,
                "action": context.action,
                "resource_type": resource.type,
                "resource_id": resource.id,
                "effect": decision.effect,
                "matched_rules": decision.matched_rules,
                "policy_version": decision.policy_version,
                "context": {"ip": context.ip_address},
            }
        )
        await db.commit()
    except Exception as e:
        log.warning("[ABAC] Failed to log decision: %s", e)
