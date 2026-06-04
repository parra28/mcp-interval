"""Tests for workout library management tools (CRUD + import/download)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from intervals_icu_mcp.tools.workout_management import (
    create_multiple_workouts,
    create_workout,
    delete_workout,
    download_event_workout,
    download_workout,
    download_workout_global,
    download_workouts_zip,
    duplicate_workouts,
    get_workout,
    import_workout,
    list_workouts,
    update_workout,
)

ATHLETE = "i123456"


def _ctx(mock_config):
    ctx = MagicMock()
    ctx.get_state = AsyncMock(return_value=mock_config)
    return ctx


@pytest.mark.asyncio
class TestListWorkouts:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/workouts").mock(
            return_value=Response(
                200,
                json=[
                    {"id": 1, "name": "VO2max", "type": "Ride", "icu_training_load": 80},
                    {"id": 2, "name": "Easy", "type": "Ride"},
                ],
            )
        )
        result = await list_workouts(ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["count"] == 2
        assert response["data"]["workouts"][0]["name"] == "VO2max"

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/workouts").mock(return_value=Response(500))
        result = await list_workouts(ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestGetWorkout:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/workouts/5").mock(
            return_value=Response(200, json={"id": 5, "name": "Threshold", "type": "Ride"})
        )
        result = await get_workout(workout_id=5, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["id"] == 5
        assert response["data"]["name"] == "Threshold"

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/workouts/5").mock(return_value=Response(404))
        result = await get_workout(workout_id=5, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestCreateWorkout:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.post(f"/athlete/{ATHLETE}/workouts").mock(
            return_value=Response(200, json={"id": 10, "name": "New", "folder_id": 3})
        )
        result = await create_workout(
            workout_json='{"name": "New", "folder_id": 3}', ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["id"] == 10

    async def test_invalid_json(self, mock_config):
        result = await create_workout(workout_json="{not json", ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "validation_error"

    async def test_non_object_payload(self, mock_config):
        result = await create_workout(workout_json="[1,2,3]", ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "validation_error"


@pytest.mark.asyncio
class TestCreateMultipleWorkouts:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.post(f"/athlete/{ATHLETE}/workouts/bulk").mock(
            return_value=Response(200, json=[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
        )
        result = await create_multiple_workouts(
            workouts_json='[{"name": "A"}, {"name": "B"}]', ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["count"] == 2

    async def test_non_array(self, mock_config):
        result = await create_multiple_workouts(workouts_json='{"name": "A"}', ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "validation_error"


@pytest.mark.asyncio
class TestUpdateWorkout:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.put(f"/athlete/{ATHLETE}/workouts/7").mock(
            return_value=Response(200, json={"id": 7, "name": "Renamed"})
        )
        result = await update_workout(
            workout_id=7, workout_json='{"name": "Renamed"}', ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["name"] == "Renamed"

    async def test_invalid_json(self, mock_config):
        result = await update_workout(workout_id=7, workout_json="bad", ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "validation_error"


@pytest.mark.asyncio
class TestDeleteWorkout:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.delete(f"/athlete/{ATHLETE}/workouts/9").mock(return_value=Response(200))
        result = await delete_workout(workout_id=9, ctx=_ctx(mock_config))
        response = json.loads(result)
        assert response["data"]["deleted"] is True
        assert response["data"]["workout_id"] == 9

    async def test_others_param(self, mock_config, respx_mock):
        route = respx_mock.delete(f"/athlete/{ATHLETE}/workouts/9").mock(
            return_value=Response(200)
        )
        await delete_workout(workout_id=9, others=True, ctx=_ctx(mock_config))
        assert "others=true" in str(route.calls.last.request.url)

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.delete(f"/athlete/{ATHLETE}/workouts/9").mock(return_value=Response(404))
        result = await delete_workout(workout_id=9, ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestDuplicateWorkouts:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.post(f"/athlete/{ATHLETE}/duplicate-workouts").mock(
            return_value=Response(200, json={"duplicated": 3})
        )
        result = await duplicate_workouts(
            payload_json='{"workout_ids": [1,2,3]}', ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["result"]["duplicated"] == 3

    async def test_invalid_json(self, mock_config):
        result = await duplicate_workouts(payload_json="oops", ctx=_ctx(mock_config))
        assert json.loads(result)["error"]["type"] == "validation_error"


@pytest.mark.asyncio
class TestImportWorkout:
    async def test_success(self, mock_config, respx_mock):
        route = respx_mock.post(f"/athlete/{ATHLETE}/folders/4/import-workout").mock(
            return_value=Response(200, json={"id": 22, "name": "Imported"})
        )
        result = await import_workout(
            folder_id=4,
            sport_type="Ride",
            file_json='{"filename": "w.zwo", "contents": "..."}',
            ctx=_ctx(mock_config),
        )
        response = json.loads(result)
        assert response["data"]["result"]["id"] == 22
        assert "type=Ride" in str(route.calls.last.request.url)

    async def test_invalid_json(self, mock_config):
        result = await import_workout(
            folder_id=4, sport_type="Ride", file_json="nope", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"


@pytest.mark.asyncio
class TestDownloadWorkoutsZip:
    async def test_success_base64(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/workouts.zip").mock(
            return_value=Response(200, content=b"PK\x03\x04zipdata")
        )
        result = await download_workouts_zip(
            oldest="2026-01-01", newest="2026-01-31", ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["format"] == "ZIP"
        assert "content_base64" in response["data"]

    async def test_api_error(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/workouts.zip").mock(return_value=Response(404))
        result = await download_workouts_zip(
            oldest="2026-01-01", newest="2026-01-31", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "api_error"


@pytest.mark.asyncio
class TestDownloadWorkout:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.post(f"/athlete/{ATHLETE}/download-workout.zwo").mock(
            return_value=Response(200, content=b"<workout_file/>")
        )
        result = await download_workout(
            workout_json='{"name": "x"}', file_format="zwo", ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["format"] == "ZWO"

    async def test_invalid_format(self, mock_config):
        result = await download_workout(
            workout_json='{"name": "x"}', file_format="pdf", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"

    async def test_invalid_json(self, mock_config):
        result = await download_workout(
            workout_json="bad", file_format="zwo", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"


@pytest.mark.asyncio
class TestDownloadEventWorkout:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.get(f"/athlete/{ATHLETE}/events/55/download.fit").mock(
            return_value=Response(200, content=b"FITDATA")
        )
        result = await download_event_workout(
            event_id=55, file_format="fit", ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["format"] == "FIT"

    async def test_invalid_format(self, mock_config):
        result = await download_event_workout(
            event_id=55, file_format="docx", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"


@pytest.mark.asyncio
class TestDownloadWorkoutGlobal:
    async def test_success(self, mock_config, respx_mock):
        respx_mock.post("/download-workout.erg").mock(
            return_value=Response(200, content=b"ergdata")
        )
        result = await download_workout_global(
            workout_json='{"name": "x"}', file_format="erg", ctx=_ctx(mock_config)
        )
        response = json.loads(result)
        assert response["data"]["format"] == "ERG"

    async def test_invalid_format(self, mock_config):
        result = await download_workout_global(
            workout_json='{"name": "x"}', file_format="txt", ctx=_ctx(mock_config)
        )
        assert json.loads(result)["error"]["type"] == "validation_error"
