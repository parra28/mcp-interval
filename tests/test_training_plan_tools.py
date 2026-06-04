"""Tests for the high-level create_training_plan tool."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from intervals_icu_mcp.tools.training_plan import create_training_plan

ATHLETE = "i123456"


def _ctx(mock_config):
    ctx = MagicMock()
    ctx.get_state = AsyncMock(return_value=mock_config)
    return ctx


PLAN_ITEMS = [
    {
        "category": "NOTE",
        "start_date_local": "2026-05-18T05:30:00",
        "name": "Phase 1",
        "description": "Base phase",
        "distance": 28,
    },
    {
        "category": "WORKOUT",
        "start_date_local": "2026-05-18T07:00:00",
        "name": "Z2 ride",
        "type": "VirtualRide",
        "description": "Warmup\n- 10m 60%",
    },
    {
        "category": "WORKOUT",
        "start_date_local": "2026-05-20T07:00:00",
        "name": "Intervals",
        "type": "VirtualRide",
        "description": "4x4min",
    },
]


@pytest.mark.asyncio
class TestCreateTrainingPlan:
    async def test_success_creates_folder_and_bulk_uploads(self, mock_config, respx_mock):
        folder_route = respx_mock.post(f"/athlete/{ATHLETE}/folders").mock(
            return_value=Response(200, json={"id": 999, "name": "My Plan", "type": "PLAN"})
        )
        bulk_route = respx_mock.post(f"/athlete/{ATHLETE}/workouts/bulk").mock(
            return_value=Response(200, json=[{"id": 1}, {"id": 2}, {"id": 3}])
        )

        result = await create_training_plan(
            plan_name="My Plan",
            items_json=json.dumps(PLAN_ITEMS),
            ctx=_ctx(mock_config),
        )
        response = json.loads(result)

        assert folder_route.called
        assert bulk_route.called
        data = response["data"]
        assert data["folder_id"] == 999
        assert data["base_date"] == "2026-05-18T05:30:00"
        assert data["total_items"] == 3
        assert data["workouts"] == 2
        assert data["notes"] == 1
        assert data["created"] == 3

    async def test_payload_transformation(self, mock_config, respx_mock):
        """day offset, NOTE type, distance->days, and folder_id are applied."""
        respx_mock.post(f"/athlete/{ATHLETE}/folders").mock(
            return_value=Response(200, json={"id": 999, "name": "P"})
        )
        bulk_route = respx_mock.post(f"/athlete/{ATHLETE}/workouts/bulk").mock(
            return_value=Response(200, json=[{"id": 1}, {"id": 2}, {"id": 3}])
        )

        await create_training_plan(
            plan_name="P", items_json=json.dumps(PLAN_ITEMS), ctx=_ctx(mock_config)
        )

        sent = json.loads(bulk_route.calls.last.request.content)
        note, wo1, wo2 = sent[0], sent[1], sent[2]

        # NOTE transformations
        assert note["type"] == "NOTE"
        assert note["days"] == 28
        assert "distance" not in note
        assert note["day"] == 0
        # category stripped from every item
        assert all("category" not in it for it in sent)
        # day offset relative to base date (2026-05-18)
        assert wo1["day"] == 0
        assert wo2["day"] == 2
        # folder_id attached
        assert all(it["folder_id"] == 999 for it in sent)

    async def test_empty_plan_name(self, mock_config):
        result = await create_training_plan(
            plan_name="   ", items_json=json.dumps(PLAN_ITEMS), ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"

    async def test_invalid_json(self, mock_config):
        result = await create_training_plan(
            plan_name="P", items_json="{not json", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"

    async def test_not_an_array(self, mock_config):
        result = await create_training_plan(
            plan_name="P", items_json='{"category": "WORKOUT"}', ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"

    async def test_empty_items(self, mock_config):
        result = await create_training_plan(
            plan_name="P", items_json="[]", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"

    async def test_missing_required_fields_reported(self, mock_config):
        bad_items = [
            {"category": "WORKOUT", "name": "No date"},  # missing start_date_local
            {"category": "NOTE", "start_date_local": "2026-05-18T05:30:00"},  # missing name
            {"start_date_local": "2026-05-18T07:00:00", "name": "No category"},  # missing category
        ]
        result = await create_training_plan(
            plan_name="P", items_json=json.dumps(bad_items), ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["error"]["type"] == "validation_error"
        suggestions = response["error"]["suggestions"]
        assert any("start_date_local" in s for s in suggestions)
        assert any("name" in s for s in suggestions)
        assert any("category" in s for s in suggestions)

    async def test_invalid_category_reported(self, mock_config):
        bad_items = [
            {"category": "RACE", "start_date_local": "2026-05-18T07:00:00", "name": "x"},
        ]
        result = await create_training_plan(
            plan_name="P", items_json=json.dumps(bad_items), ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["error"]["type"] == "validation_error"
        assert any("RACE" in s for s in response["error"]["suggestions"])

    async def test_api_error_on_folder(self, mock_config, respx_mock):
        respx_mock.post(f"/athlete/{ATHLETE}/folders").mock(return_value=Response(500))
        result = await create_training_plan(
            plan_name="P", items_json=json.dumps(PLAN_ITEMS), ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "api_error"
