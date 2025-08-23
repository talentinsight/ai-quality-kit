"""Authentication and authorization module with Bearer Auth and RBAC."""

import os
import hashlib
from typing import Dict, Optional, List, Set
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

# Global security instance
security = HTTPBearer(auto_error=False)


class Principal:
    """Represents an authenticated principal."""
    
    def __init__(self, role: str, token_hash_prefix: str):
        self.role = role
        self.token_hash_prefix = token_hash_prefix


def _parse_auth_tokens() -> Dict[str, str]:
    """Parse AUTH_TOKENS environment variable into token->role mapping."""
    auth_tokens_str = os.getenv("AUTH_TOKENS", "")
    if not auth_tokens_str:
        return {}
    
    token_role_map = {}
    for token_role in auth_tokens_str.split(","):
        token_role = token_role.strip()
        if ":" in token_role:
            role, token = token_role.split(":", 1)
            token_role_map[token.strip()] = role.strip()
    
    return token_role_map


def _parse_rbac_routes() -> Dict[str, Set[str]]:
    """Parse RBAC_ALLOWED_ROUTES into route->allowed_roles mapping."""
    rbac_str = os.getenv("RBAC_ALLOWED_ROUTES", "")
    if not rbac_str:
        return {}
    
    route_roles_map = {}
    for route_roles in rbac_str.split(","):
        route_roles = route_roles.strip()
        if ":" in route_roles:
            route, roles_str = route_roles.split(":", 1)
            roles = set(role.strip() for role in roles_str.split("|"))
            route_roles_map[route.strip()] = roles
    
    return route_roles_map


def _get_token_hash_prefix(token: str) -> str:
    """Get short hash prefix for logging (never log raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()[:8]


def get_principal(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Principal]:
    """
    Get authenticated principal from Bearer token.
    
    Returns:
        Principal if authenticated, None if AUTH_ENABLED=false, raises 401 if auth required but missing/invalid
    """
    auth_enabled = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    
    if not auth_enabled:
        # Auth disabled - return None to indicate no-op
        return None
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    token_role_map = _parse_auth_tokens()
    
    if token not in token_role_map:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    role = token_role_map[token]
    token_hash_prefix = _get_token_hash_prefix(token)
    
    return Principal(role=role, token_hash_prefix=token_hash_prefix)


def require_role(*allowed_roles: str):
    """
    Dependency factory that requires specific roles.
    
    Args:
        allowed_roles: Roles that are allowed to access the endpoint
        
    Returns:
        Dependency function that validates role access
    """
    def role_checker(principal: Optional[Principal] = Depends(get_principal)) -> Optional[Principal]:
        auth_enabled = os.getenv("AUTH_ENABLED", "false").lower() == "true"
        
        if not auth_enabled:
            # Auth disabled - no-op
            return None
        
        if not principal:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        if principal.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        
        return principal
    
    return role_checker


def check_route_access(path: str, principal: Optional[Principal]) -> bool:
    """
    Check if principal has access to a specific route path.
    
    Args:
        path: Request path to check
        principal: Authenticated principal (None if auth disabled)
        
    Returns:
        True if access allowed, False otherwise
    """
    auth_enabled = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    
    if not auth_enabled:
        return True
    
    if not principal:
        return False
    
    route_roles_map = _parse_rbac_routes()
    
    # Check exact match first
    if path in route_roles_map:
        return principal.role in route_roles_map[path]
    
    # Check wildcard matches (e.g., /orchestrator/* matches /orchestrator/run_tests)
    for route_pattern, allowed_roles in route_roles_map.items():
        if route_pattern.endswith("/*"):
            prefix = route_pattern[:-2]  # Remove /*
            if path.startswith(prefix):
                return principal.role in allowed_roles
    
    # Default deny if no match found
    return False


# Convenience functions for common role checks
def require_user_or_admin():
    """Require user or admin role."""
    return require_role("user", "admin")


def require_admin():
    """Require admin role only."""
    return require_role("admin")
