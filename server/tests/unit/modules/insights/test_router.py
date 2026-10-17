"""Insights routes: the rate limit is counted per signed-in user, not per address."""

import importlib

import pytest

from app.core.limiter import limiter, user_or_ip_key

# The module, not the package root's `router` (the APIRouter it re-exports).
routes = importlib.import_module("app.modules.insights.router")

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("route", [routes.get_insights, routes.generate_insights])
def test_the_limit_is_keyed_per_user(route):
    limits = limiter._route_limits[f"{route.__module__}.{route.__name__}"]
    assert [limit.key_func for limit in limits] == [user_or_ip_key]
