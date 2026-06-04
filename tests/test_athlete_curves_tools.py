"""Tests for the athlete power-hr-curve and MMP-model tools."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from intervals_icu_mcp.tools.performance import get_mmp_model, get_power_hr_curve

ATHLETE = "i123456"


def _ctx(mock_config):
    ctx = MagicMock()
    ctx.get_state = AsyncMock(return_value=mock_config)
    return ctx


@pytest.mark.asyncio
class TestPowerHrCurve:
    async def test_success(self, mock_config, respx_mock):
        route = respx_mock.get(f"/athlete/{ATHLETE}/power-hr-curve").mock(
            return_value=Response(200, json={"watts": [200, 250], "bpm": [140, 160]})
        )
        result = await get_power_hr_curve(
            start_date="2026-01-01", end_date="2026-03-01", ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["power_hr_curve"]["watts"] == [200, 250]
        assert response["data"]["start"] == "2026-01-01"
        url = str(route.calls.last.request.url)
        assert "start=2026-01-01" in url
        assert "end=2026-03-01" in url

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/power-hr-curve").mock(return_value=Response(404))
        result = await get_power_hr_curve(
            start_date="2026-01-01", end_date="2026-03-01", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestMmpModel:
    async def test_success(self, mock_config, respx_mock):
        route = respx_mock.get(f"/athlete/{ATHLETE}/mmp-model").mock(
            return_value=Response(200, json={"cp": 280, "w_prime": 20000})
        )
        result = await get_mmp_model(sport_type="Ride", ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["mmp_model"]["cp"] == 280
        assert response["data"]["sport_type"] == "Ride"
        assert "type=Ride" in str(route.calls.last.request.url)

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/mmp-model").mock(return_value=Response(500))
        result = await get_mmp_model(sport_type="Run", ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"
