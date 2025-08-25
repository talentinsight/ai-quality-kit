"""Authentication and authorization module with Bearer Auth, JWT, and RBAC."""

import os
import hashlib
import jwt
import requests
import time
from typing import Dict, Optional, List, Set, Any, Union
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from datetime import datetime, timezone

from apps.audit import audit_auth_failure

load_dotenv()

# Global security instance
security = HTTPBearer(auto_error=False)

# JWKS cache with TTL
_jwks_cache: Dict[str, Dict[str, Any]] = {}
JWKS_CACHE_TTL = 600  # 10 minutes


class Principal:
    """Represents an authenticated principal."""
    
    def __init__(self, role: str, token_hash_prefix: str, claims: Optional[Dict[str, Any]] = None):
        self.role = role
        self.token_hash_prefix = token_hash_prefix
        self.claims = claims or {}


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


def _get_auth_mode() -> str:
    """Get the authentication mode from environment."""
    return os.getenv("AUTH_MODE", "token").lower()


def _get_jwt_config() -> Dict[str, Optional[str]]:
    """Get JWT configuration from environment variables."""
    return {
        "secret": os.getenv("JWT_SECRET"),
        "jwks_url": os.getenv("JWT_JWKS_URL"),
        "issuer": os.getenv("JWT_ISSUER"),
        "audience": os.getenv("JWT_AUDIENCE"),
    }


def _fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    """Fetch JWKS from the provided URL with caching."""
    current_time = time.time()
    
    # Check cache first
    if jwks_url in _jwks_cache:
        cached_entry = _jwks_cache[jwks_url]
        if current_time - cached_entry["timestamp"] < JWKS_CACHE_TTL:
            return cached_entry["jwks"]
    
    try:
        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()
        jwks = response.json()
        
        # Cache the result
        _jwks_cache[jwks_url] = {
            "jwks": jwks,
            "timestamp": current_time
        }
        
        return jwks
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Failed to fetch JWKS",
            headers={"WWW-Authenticate": "Bearer"}
        ) from e


def _get_jwt_key(token: str, jwt_config: Dict[str, Optional[str]]) -> Union[str, Any]:
    """Get the key for JWT validation (either secret or from JWKS)."""
    if jwt_config["secret"]:
        return jwt_config["secret"]
    
    if jwt_config["jwks_url"]:
        # Decode header to get kid
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise HTTPException(
                    status_code=401,
                    detail="JWT missing kid in header",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Fetch JWKS and find the key
            jwks = _fetch_jwks(jwt_config["jwks_url"])
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    # Convert JWK to PEM format for RS256
                    from jwt.algorithms import RSAAlgorithm
                    return RSAAlgorithm.from_jwk(key)
            
            raise HTTPException(
                status_code=401,
                detail="JWT kid not found in JWKS",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=401,
                detail="Invalid JWT format",
                headers={"WWW-Authenticate": "Bearer"}
            ) from e
    
    raise HTTPException(
        status_code=401,
        detail="JWT configuration missing",
        headers={"WWW-Authenticate": "Bearer"}
    )


def _extract_roles_from_jwt(claims: Dict[str, Any]) -> List[str]:
    """Extract roles from JWT claims."""
    # Try 'roles' field first (array)
    if "roles" in claims and isinstance(claims["roles"], list):
        return claims["roles"]
    
    # Try 'scope' field (space-delimited string)
    if "scope" in claims and isinstance(claims["scope"], str):
        return claims["scope"].split()
    
    # Default to empty list if no roles found
    return []


def _validate_jwt_token(token: str) -> Principal:
    """Validate JWT token and return Principal."""
    jwt_config = _get_jwt_config()
    
    # In JWT mode, issuer and audience are REQUIRED
    if not jwt_config["issuer"]:
        raise HTTPException(
            status_code=401,
            detail={"error": "configuration_error", "message": "JWT_ISSUER is required in JWT mode"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not jwt_config["audience"]:
        raise HTTPException(
            status_code=401,
            detail={"error": "configuration_error", "message": "JWT_AUDIENCE is required in JWT mode"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        # Get the key for validation
        key = _get_jwt_key(token, jwt_config)
        
        # Determine algorithm
        algorithm = "HS256" if jwt_config["secret"] else "RS256"
        
        # Prepare validation options - always validate iss and aud in JWT mode
        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_nbf": True,
            "verify_iss": True,
            "verify_aud": True,
        }
        
        # Decode and validate the JWT
        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            issuer=jwt_config["issuer"],
            audience=jwt_config["audience"],
            options=decode_options
        )
        
        # Extract roles from claims
        roles = _extract_roles_from_jwt(claims)
        
        # Reject tokens with no roles
        if not roles:
            raise HTTPException(
                status_code=401,
                detail={"error": "insufficient_permissions", "message": "Token contains no roles"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Use the first role as the primary role (for compatibility)
        primary_role = roles[0]
        
        # Generate token hash prefix for logging (never echo full token)
        token_hash_prefix = _get_token_hash_prefix(token)
        
        return Principal(
            role=primary_role,
            token_hash_prefix=token_hash_prefix,
            claims=claims
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"error": "token_expired", "message": "Token has expired"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_issuer", "message": "Token issuer does not match expected value"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_audience", "message": "Token audience does not match expected value"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": "Token validation failed"},
            headers={"WWW-Authenticate": "Bearer"}
        ) from e
    except HTTPException:
        # Re-raise HTTPExceptions from helper functions (like missing kid)
        raise
    except Exception as e:
        # Log the error but don't expose internal details
        print(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"}
        ) from e


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    # Check X-Forwarded-For header first (for proxy/load balancer scenarios)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def get_principal_with_audit(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Principal]:
    """
    Get authenticated principal with audit logging.
    
    Returns:
        Principal if authenticated, None if AUTH_ENABLED=false, raises 401 if auth required but missing/invalid
    """
    auth_enabled = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    client_ip = _get_client_ip(request)
    route = request.url.path
    
    if not auth_enabled:
        # Auth disabled - return None to indicate no-op
        return None
    
    if not credentials:
        audit_auth_failure(
            reason="missing_token",
            ip=client_ip,
            route=route
        )
        raise HTTPException(
            status_code=401,
            detail={"error": "missing_token", "message": "Bearer token required"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    token_prefix = _get_token_hash_prefix(token)
    auth_mode = _get_auth_mode()
    
    try:
        if auth_mode == "jwt":
            # JWT authentication mode
            return _validate_jwt_token(token)
        
        elif auth_mode == "token":
            # Traditional token authentication mode
            token_role_map = _parse_auth_tokens()
            
            if token not in token_role_map:
                audit_auth_failure(
                    reason="invalid_token",
                    ip=client_ip,
                    route=route,
                    token_prefix=token_prefix
                )
                raise HTTPException(
                    status_code=401,
                    detail={"error": "invalid_token", "message": "Token not recognized"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            role = token_role_map[token]
            
            return Principal(role=role, token_hash_prefix=token_prefix)
        
        else:
            audit_auth_failure(
                reason="invalid_auth_mode",
                ip=client_ip,
                route=route
            )
            raise HTTPException(
                status_code=401,
                detail={"error": "configuration_error", "message": "Invalid authentication mode"},
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    except HTTPException as e:
        # If this is a JWT validation error, audit it
        if e.status_code == 401:
            error_detail = e.detail
            if isinstance(error_detail, dict):
                reason = error_detail.get("error", "jwt_validation_failed")
            else:
                reason = "jwt_validation_failed"
            
            audit_auth_failure(
                reason=reason,
                ip=client_ip,
                route=route,
                token_prefix=token_prefix
            )
        raise


def get_principal(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Principal]:
    """
    Legacy get_principal function for backward compatibility.
    Note: This version does not include audit logging.
    """
    auth_enabled = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    
    if not auth_enabled:
        return None
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail={"error": "missing_token", "message": "Bearer token required"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    auth_mode = _get_auth_mode()
    
    if auth_mode == "jwt":
        return _validate_jwt_token(token)
    elif auth_mode == "token":
        token_role_map = _parse_auth_tokens()
        
        if token not in token_role_map:
            raise HTTPException(
                status_code=401,
                detail={"error": "invalid_token", "message": "Token not recognized"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
        role = token_role_map[token]
        token_hash_prefix = _get_token_hash_prefix(token)
        
        return Principal(role=role, token_hash_prefix=token_hash_prefix)
    
    else:
        raise HTTPException(
            status_code=401,
            detail={"error": "configuration_error", "message": "Invalid authentication mode"},
            headers={"WWW-Authenticate": "Bearer"}
        )


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
