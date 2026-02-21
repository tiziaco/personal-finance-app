"""System health and status endpoints.

This module provides infrastructure endpoints for monitoring application health,
status, and basic information.
"""

from datetime import datetime
from typing import (
    Any,
    Dict,
)

from fastapi import (
    APIRouter,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.dependencies.auth import CurrentUser
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.database.engine import health_check as db_health_check

router = APIRouter(tags=["system"])


@router.get(
    "/",
    summary="Get API information",
    description="Retrieve basic API metadata including version, environment, and documentation URLs."
)
@limiter.limit(settings.rate_limits.endpoints.ROOT[0])
async def root(request: Request) -> Dict[str, Any]:
    """Root endpoint returning basic API information.
    
    Returns:
        Dict[str, Any]: Basic API information
    """
    logger.info("root_endpoint_called")
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "environment": settings.ENVIRONMENT.value,
        "swagger_url": "/docs",
        "redoc_url": "/redoc",
    }


@router.get(
    "/health",
    summary="Check API health status",
    description="Minimal public health check endpoint for container orchestration and load balancers. Returns basic status without sensitive details."
)
@limiter.limit(settings.rate_limits.endpoints.HEALTH[0])
async def health_check(request: Request) -> Dict[str, Any]:
    """Minimal public health check endpoint.
    
    This endpoint is designed for container orchestrators (Docker, ECS, Kubernetes)
    and load balancers. It performs actual health checks but returns minimal
    information without exposing sensitive details about the system architecture.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict[str, Any]: Minimal health status
        
    Status Codes:
        200: System is healthy and ready to serve requests
        503: System is degraded or unavailable
    """
    logger.info("health_check_called")

    # Get database engine from app state
    engine: AsyncEngine = request.app.state.engine
    
    # Check database connectivity
    db_healthy = await db_health_check(engine)
    
    # Check agent readiness
    agents_healthy = False
    
    if hasattr(request.app.state, "agents"):
        agents_healthy = True
        for agent_name, agent_instance in request.app.state.agents.items():
            if not agent_instance.is_ready():
                agents_healthy = False
                break
    
    # Overall health is healthy only if both DB and agents are healthy
    overall_healthy = db_healthy and agents_healthy

    response = {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
    }

    # If DB or agents are unhealthy, set the appropriate status code
    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(content=response, status_code=status_code)


@router.get(
    "/ready",
    summary="Get detailed readiness status",
    description="Detailed readiness check with component-level health information. Requires authentication. Use this endpoint for monitoring dashboards and operational visibility."
)
@limiter.limit(settings.rate_limits.endpoints.READY[0])
async def readiness_check(user: CurrentUser, request: Request) -> Dict[str, Any]:
    """Detailed readiness check endpoint for authenticated operations teams.
    
    This endpoint provides comprehensive health information including:
    - Application version and environment
    - Database connectivity and connection pool stats
    - Agent readiness and graph compilation status
    - Component-level health details
    
    Requires authentication via JWT token.
    
    Args:
        user: Authenticated user (from CurrentUser dependency)
        request: FastAPI request object
        
    Returns:
        Dict[str, Any]: Detailed readiness status information
        
    Status Codes:
        200: System is healthy and ready
        503: System is degraded or unavailable
    """
    logger.info("readiness_check_called", user_id=user.id)

    # Get database engine from app state
    engine: AsyncEngine = request.app.state.engine
    
    # Check database connectivity
    db_healthy = await db_health_check(engine)
    
    # Get connection pool stats
    pool_stats = {
        "size": engine.pool.size(),
        "checked_in": engine.pool.checkedin(),
        "checked_out": engine.pool.checkedout(),
        "overflow": engine.pool.overflow(),
        "total": engine.pool.size() + engine.pool.overflow(),
    }
    
    # Check agent readiness
    agents_status = {}
    agents_healthy = False
    
    if hasattr(request.app.state, "agents"):
        agents_healthy = True
        for agent_name, agent_instance in request.app.state.agents.items():
            is_ready = agent_instance.is_ready()
            agents_status[agent_name] = {
                "ready": is_ready,
                "graph_compiled": is_ready,
            }
            if not is_ready:
                agents_healthy = False
    else:
        agents_healthy = False
        agents_status["error"] = "Agents not initialized"

    # Overall health is healthy only if both DB and agents are healthy
    overall_healthy = db_healthy and agents_healthy

    response = {
        "status": "healthy" if overall_healthy else "degraded",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT.value,
        "components": {
            "api": "healthy",
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "connection_pool": pool_stats,
            },
            "agents": agents_status if agents_healthy else {"status": "unhealthy", "details": agents_status},
        },
        "timestamp": datetime.now().isoformat(),
    }

    # If DB or agents are unhealthy, set the appropriate status code
    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(content=response, status_code=status_code)
