"""Tests for the extended activity-analysis tools.

Covers the per-activity endpoints added on top of the original analysis set:
time-at-HR, weather summary, HR load model, power-spike model, power-vs-HR,
and the per-activity HR / pace / power curves. These endpoints return
variable-shape JSON, so the tools wrap the raw payload under a named key.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from intervals_icu_mcp.tools.activity_analysis import (
    get_activity_hr_curve,
    get_activity_hr_load_model,
    get_activity_pace_curve,
    get_activity_power_curve,
    get_activity_power_curves,
    get_activity_power_spike_model,
    get_activity_power_vs_hr,
    get_activity_time_at_hr,
    get_activity_weather_summary,
)

ACTIVITY_ID = "i123"


def _ctx(mock_config):
    ctx = MagicMock()
    ctx.get_state = AsyncMock(return_value=mock_config)
    return ctx


@pytest.mark.asyncio
class TestTimeAtHr:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/time-at-hr").mock(
            return_value=Response(200, json={"zones": [10, 20, 30]})
        )
        result = await get_activity_time_at_hr(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["activity_id"] == ACTIVITY_ID
        assert response["data"]["time_at_hr"] == {"zones": [10, 20, 30]}

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/time-at-hr").mock(return_value=Response(404))
        result = await get_activity_time_at_hr(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestWeatherSummary:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/weather-summary").mock(
            return_value=Response(200, json={"average_temp": 18.5, "average_wind_speed": 12})
        )
        result = await get_activity_weather_summary(
            activity_id=ACTIVITY_ID, ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["weather"]["average_temp"] == 18.5

    async def test_passes_index_range(self, mock_config, respx_mock):
        route = respx_mock.get(f"/activity/{ACTIVITY_ID}/weather-summary").mock(
            return_value=Response(200, json={})
        )
        await get_activity_weather_summary(
            activity_id=ACTIVITY_ID, start_index=10, end_index=99, ctx=_ctx(mock_config)
        )
        assert route.called
        request = route.calls.last.request
        assert "start_index=10" in str(request.url)
        assert "end_index=99" in str(request.url)

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/weather-summary").mock(
            return_value=Response(404)
        )
        result = await get_activity_weather_summary(
            activity_id=ACTIVITY_ID, ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestHrLoadModel:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/hr-load-model").mock(
            return_value=Response(200, json={"hr_load": 42})
        )
        result = await get_activity_hr_load_model(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["hr_load_model"]["hr_load"] == 42

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/hr-load-model").mock(return_value=Response(404))
        result = await get_activity_hr_load_model(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestPowerSpikeModel:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-spike-model").mock(
            return_value=Response(200, json={"threshold": 1500})
        )
        result = await get_activity_power_spike_model(
            activity_id=ACTIVITY_ID, ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["power_spike_model"]["threshold"] == 1500

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-spike-model").mock(
            return_value=Response(500)
        )
        result = await get_activity_power_spike_model(
            activity_id=ACTIVITY_ID, ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestPowerVsHr:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-vs-hr").mock(
            return_value=Response(200, json={"points": [[100, 120]]})
        )
        result = await get_activity_power_vs_hr(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["power_vs_hr"]["points"] == [[100, 120]]

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-vs-hr").mock(return_value=Response(404))
        result = await get_activity_power_vs_hr(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestActivityHrCurve:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/hr-curve").mock(
            return_value=Response(200, json={"secs": [5, 60], "bpm": [180, 170]})
        )
        result = await get_activity_hr_curve(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["hr_curve"]["bpm"] == [180, 170]

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/hr-curve").mock(return_value=Response(404))
        result = await get_activity_hr_curve(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestActivityPaceCurve:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/pace-curve").mock(
            return_value=Response(200, json={"secs": [5, 60], "pace": [3.2, 3.8]})
        )
        result = await get_activity_pace_curve(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["use_gap"] is False
        assert response["data"]["pace_curve"]["pace"] == [3.2, 3.8]

    async def test_use_gap_sets_param(self, mock_config, respx_mock):
        route = respx_mock.get(f"/activity/{ACTIVITY_ID}/pace-curve").mock(
            return_value=Response(200, json={})
        )
        result = await get_activity_pace_curve(
            activity_id=ACTIVITY_ID, use_gap=True, ctx=_ctx(mock_config)
        )
        assert route.called
        assert "gap=true" in str(route.calls.last.request.url)
        assert json.loads(result)["data"]["use_gap"] is True

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/pace-curve").mock(return_value=Response(404))
        result = await get_activity_pace_curve(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestActivityPowerCurve:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-curve").mock(
            return_value=Response(200, json={"secs": [5, 60], "watts": [800, 400]})
        )
        result = await get_activity_power_curve(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["power_curve"]["watts"] == [800, 400]

    async def test_fatigue_param(self, mock_config, respx_mock):
        route = respx_mock.get(f"/activity/{ACTIVITY_ID}/power-curve").mock(
            return_value=Response(200, json={})
        )
        await get_activity_power_curve(
            activity_id=ACTIVITY_ID, fatigue="fresh", ctx=_ctx(mock_config)
        )
        assert "fatigue=fresh" in str(route.calls.last.request.url)

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-curve").mock(return_value=Response(404))
        result = await get_activity_power_curve(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestActivityPowerCurves:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-curves").mock(
            return_value=Response(200, json={"watts": {"secs": [5], "values": [800]}})
        )
        result = await get_activity_power_curves(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert "watts" in response["data"]["power_curves"]

    async def test_types_param(self, mock_config, respx_mock):
        route = respx_mock.get(f"/activity/{ACTIVITY_ID}/power-curves").mock(
            return_value=Response(200, json={})
        )
        await get_activity_power_curves(
            activity_id=ACTIVITY_ID, types=["watts", "watts_alt"], ctx=_ctx(mock_config)
        )
        url = str(route.calls.last.request.url)
        assert "types=watts" in url

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/activity/{ACTIVITY_ID}/power-curves").mock(return_value=Response(404))
        result = await get_activity_power_curves(activity_id=ACTIVITY_ID, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"
