"""Shared HTTP clients for external service calls."""

import asyncio
import httpx
from typing import Optional

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseHTTPClient:
    """Base singleton HTTPX client with connection pooling."""

    _instance: Optional[httpx.AsyncClient] = None
    _semaphore: Optional[asyncio.Semaphore] = None

    MAX_CONCURRENT_REQUESTS = 10
    MAX_KEEPALIVE_CONNECTIONS = 10
    MAX_CONNECTIONS = 20
    KEEPALIVE_EXPIRY = 30.0
    TIMEOUT_CONNECT = 10.0
    TIMEOUT_READ = 60.0
    TIMEOUT_WRITE = 10.0
    TIMEOUT_POOL = 5.0
    CLIENT_NAME = "Base"

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """Get or create the shared HTTPX async client.

        Returns:
            httpx.AsyncClient: Configured async HTTP client with connection pooling
        """
        if cls._instance is None:
            limits = httpx.Limits(
                max_keepalive_connections=cls.MAX_KEEPALIVE_CONNECTIONS,
                max_connections=cls.MAX_CONNECTIONS,
                keepalive_expiry=cls.KEEPALIVE_EXPIRY
            )

            timeout = httpx.Timeout(
                connect=cls.TIMEOUT_CONNECT,
                read=cls.TIMEOUT_READ,
                write=cls.TIMEOUT_WRITE,
                pool=cls.TIMEOUT_POOL
            )

            cls._instance = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                follow_redirects=True
            )

            cls._semaphore = asyncio.Semaphore(cls.MAX_CONCURRENT_REQUESTS)

            logger.debug(
                f"Created {cls.CLIENT_NAME} HTTPX AsyncClient with connection pooling "
                f"(max concurrent requests: {cls.MAX_CONCURRENT_REQUESTS})"
            )

        return cls._instance

    @classmethod
    def get_semaphore(cls) -> asyncio.Semaphore:
        """Get the semaphore for bounded concurrency.

        Returns:
            asyncio.Semaphore: Semaphore limiting concurrent requests
        """
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(cls.MAX_CONCURRENT_REQUESTS)
        return cls._semaphore

    @classmethod
    async def close(cls):
        """Close the shared client and cleanup connections."""
        if cls._instance is not None:
            await cls._instance.aclose()
            cls._instance = None
            cls._semaphore = None
            logger.debug(f"Closed {cls.CLIENT_NAME} HTTPX AsyncClient")


class TransactionLabelerHTTPClient(BaseHTTPClient):
    """Singleton HTTPX client for Transaction Labeler API calls with connection pooling."""

    _instance: Optional[httpx.AsyncClient] = None
    _semaphore: Optional[asyncio.Semaphore] = None

    MAX_CONCURRENT_REQUESTS = 10
    TIMEOUT_READ = 150.0
    CLIENT_NAME = "Transaction Labeler"
