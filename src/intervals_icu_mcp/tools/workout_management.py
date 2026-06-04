"""Workout library management tools (create/update/delete/download).

These complement the read-only browsing tools in `workout_library.py`
(`get_workout_library`, `get_workouts_in_folder`) with full CRUD over the
athlete's workout library plus file import/export helpers.
"""

import json
from typing import Annotated, Any, cast

from fastmcp import Context

from ..auth import ICUConfig
from ..client import ICUAPIError, ICUClient
from ..models import Workout
from ..response_builder import ResponseBuilder
from ._downloads import download_and_respond


def _workout_to_dict(workout: Workout) -> dict[str, Any]:
    """Serialize a Workout, omitting None values."""
    item: dict[str, Any] = {"id": workout.id}
    if workout.name is not None:
        item["name"] = workout.name
    if workout.description is not None:
        item["description"] = workout.description
    if workout.type is not None:
        item["type"] = workout.type
    if workout.folder_id is not None:
        item["folder_id"] = workout.folder_id
    if workout.moving_time is not None:
        item["duration_seconds"] = workout.moving_time
    if workout.distance is not None:
        item["distance_meters"] = workout.distance
    if workout.icu_training_load is not None:
        item["training_load"] = workout.icu_training_load
    if workout.icu_intensity is not None:
        item["intensity_factor"] = workout.icu_intensity
    if workout.indoor is not None:
        item["indoor"] = workout.indoor
    return item


async def list_workouts(
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """List EVERY workout in the athlete's library across all folders — flat list, no folder grouping.

    Use for "show all my workouts". To browse by folder/plan use
    icu_get_workout_library then icu_get_workouts_in_folder.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            workouts = await client.list_workouts(athlete_id=athlete_id)
            data = [_workout_to_dict(w) for w in workouts]
            return ResponseBuilder.build_response(
                data={"workouts": data, "count": len(data)},
                query_type="list_workouts",
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def get_workout(
    workout_id: Annotated[int, "Workout ID to fetch"],
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Fetch ONE workout from the library by ID — full metadata (name, type, structure, load)."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            workout = await client.get_workout(workout_id, athlete_id=athlete_id)
            return ResponseBuilder.build_response(
                data=_workout_to_dict(workout),
                query_type="get_workout",
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def create_workout(
    workout_json: Annotated[
        str, "JSON object for the workout (name, folder_id, type, description with workout DSL)"
    ],
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Create ONE new workout in a library folder or plan. For many at once use icu_create_multiple_workouts.

    The workout structure goes in the `description` field using the
    Intervals.icu workout DSL (see the intervals-icu://workout-syntax resource).
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        workout_data = json.loads(workout_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON: {str(e)}", error_type="validation_error"
        )
    if not isinstance(workout_data, dict):
        return ResponseBuilder.build_error_response(
            "Workout payload must be a JSON object", error_type="validation_error"
        )

    workout_dict = cast(dict[str, Any], workout_data)
    try:
        async with ICUClient(config) as client:
            workout = await client.create_workout(workout_dict, athlete_id=athlete_id)
            return ResponseBuilder.build_response(
                data=_workout_to_dict(workout),
                query_type="create_workout",
                metadata={"message": f"Created workout {workout.id}"},
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def create_multiple_workouts(
    workouts_json: Annotated[str, "JSON array of workout objects to create in one request"],
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Create MANY new workouts in a folder/plan in a single call. For one workout use icu_create_workout."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        workouts = json.loads(workouts_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON: {str(e)}", error_type="validation_error"
        )
    if not isinstance(workouts, list):
        return ResponseBuilder.build_error_response(
            "Payload must be a JSON array of workouts", error_type="validation_error"
        )

    workouts_list = cast(list[dict[str, Any]], workouts)
    try:
        async with ICUClient(config) as client:
            created = await client.create_multiple_workouts(workouts_list, athlete_id=athlete_id)
            data = [_workout_to_dict(w) for w in created]
            return ResponseBuilder.build_response(
                data={"workouts": data, "count": len(data)},
                query_type="create_multiple_workouts",
                metadata={"message": f"Created {len(data)} workouts"},
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def update_workout(
    workout_id: Annotated[int, "Workout ID to update"],
    workout_json: Annotated[str, "JSON object with the fields to change"],
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Update an existing library workout (rename, reconfigure structure, move folder)."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        workout_data = json.loads(workout_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON: {str(e)}", error_type="validation_error"
        )
    if not isinstance(workout_data, dict):
        return ResponseBuilder.build_error_response(
            "Workout payload must be a JSON object", error_type="validation_error"
        )

    workout_dict = cast(dict[str, Any], workout_data)
    try:
        async with ICUClient(config) as client:
            workout = await client.update_workout(
                workout_id, workout_dict, athlete_id=athlete_id
            )
            return ResponseBuilder.build_response(
                data=_workout_to_dict(workout),
                query_type="update_workout",
                metadata={"message": f"Updated workout {workout_id}"},
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def delete_workout(
    workout_id: Annotated[int, "Workout ID to delete"],
    others: Annotated[bool, "Also delete sibling workouts added at the same time on a plan"] = False,
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Delete a workout from the library. Removes a reusable template, not recorded training data."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            await client.delete_workout(workout_id, others=others, athlete_id=athlete_id)
            return ResponseBuilder.build_response(
                data={"workout_id": workout_id, "deleted": True, "others": others},
                query_type="delete_workout",
                metadata={"message": f"Deleted workout {workout_id}"},
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def duplicate_workouts(
    payload_json: Annotated[str, "JSON object describing which workouts to duplicate and where"],
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Duplicate workouts on a plan (copy existing workouts to new positions/dates)."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON: {str(e)}", error_type="validation_error"
        )
    if not isinstance(payload, dict):
        return ResponseBuilder.build_error_response(
            "Payload must be a JSON object", error_type="validation_error"
        )

    payload_dict = cast(dict[str, Any], payload)
    try:
        async with ICUClient(config) as client:
            result = await client.duplicate_workouts(payload_dict, athlete_id=athlete_id)
            return ResponseBuilder.build_response(
                data={"result": result},
                query_type="duplicate_workouts",
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def import_workout(
    folder_id: Annotated[int, "Folder ID to import the workout into"],
    sport_type: Annotated[str, "Sport type for the imported workout (e.g. Ride, Run)"],
    file_json: Annotated[str, "JSON object with the file payload (filename + contents) to import"],
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Import a workout from a .zwo / .mrc / .erg / .fit file into a library folder."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        file_payload = json.loads(file_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON: {str(e)}", error_type="validation_error"
        )
    if not isinstance(file_payload, dict):
        return ResponseBuilder.build_error_response(
            "File payload must be a JSON object", error_type="validation_error"
        )

    file_dict = cast(dict[str, Any], file_payload)
    try:
        async with ICUClient(config) as client:
            result = await client.import_workout(
                folder_id, file_dict, sport_type, athlete_id=athlete_id
            )
            return ResponseBuilder.build_response(
                data={"result": result, "folder_id": folder_id},
                query_type="import_workout",
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def download_workouts_zip(
    oldest: Annotated[str, "Oldest date (YYYY-MM-DD) of planned workouts to include"],
    newest: Annotated[str, "Newest date (YYYY-MM-DD) of planned workouts to include"],
    output_path: Annotated[str | None, "Path to save the .zip file (optional)"] = None,
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Download planned workouts in a date range as a single .zip file (saved to disk or base64)."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            content = await client.download_workouts_zip(oldest, newest, athlete_id=athlete_id)
            return download_and_respond(
                f"{oldest}_{newest}", content, output_path, "download_workouts_zip", "ZIP"
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def download_workout(
    workout_json: Annotated[str, "JSON object with the workout to convert"],
    file_format: Annotated[str, "Target format: zwo, mrc, erg or fit"] = "zwo",
    output_path: Annotated[str | None, "Path to save the file (optional)"] = None,
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Convert ONE library/athlete workout to a device file (.zwo/.mrc/.erg/.fit). For a calendar event use icu_download_event_workout."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    fmt = file_format.lower().lstrip(".")
    if fmt not in {"zwo", "mrc", "erg", "fit"}:
        return ResponseBuilder.build_error_response(
            "file_format must be one of: zwo, mrc, erg, fit", error_type="validation_error"
        )

    try:
        workout_data = json.loads(workout_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON: {str(e)}", error_type="validation_error"
        )
    if not isinstance(workout_data, dict):
        return ResponseBuilder.build_error_response(
            "Workout payload must be a JSON object", error_type="validation_error"
        )

    workout_dict = cast(dict[str, Any], workout_data)
    try:
        async with ICUClient(config) as client:
            content = await client.download_workout(
                workout_dict, f".{fmt}", athlete_id=athlete_id
            )
            return download_and_respond(
                "workout", content, output_path, "download_workout", fmt.upper()
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def download_event_workout(
    event_id: Annotated[int, "Calendar event ID whose workout to download"],
    file_format: Annotated[str, "Target format: zwo, mrc, erg or fit"] = "zwo",
    output_path: Annotated[str | None, "Path to save the file (optional)"] = None,
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Download a PLANNED (calendar) workout as a device file (.zwo/.mrc/.erg/.fit). For a library workout use icu_download_workout."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    fmt = file_format.lower().lstrip(".")
    if fmt not in {"zwo", "mrc", "erg", "fit"}:
        return ResponseBuilder.build_error_response(
            "file_format must be one of: zwo, mrc, erg, fit", error_type="validation_error"
        )

    try:
        async with ICUClient(config) as client:
            content = await client.download_event_workout(
                event_id, f".{fmt}", athlete_id=athlete_id
            )
            return download_and_respond(
                str(event_id), content, output_path, "download_event_workout", fmt.upper()
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def download_workout_global(
    workout_json: Annotated[str, "JSON object with the workout to convert"],
    file_format: Annotated[str, "Target format: zwo, mrc, erg or fit"] = "zwo",
    output_path: Annotated[str | None, "Path to save the file (optional)"] = None,
    ctx: Context | None = None,
) -> str:
    """Convert an arbitrary workout payload to a device file WITHOUT an athlete context (.zwo/.mrc/.erg/.fit).

    Use for ad-hoc conversion of a workout you supply directly. For a saved
    library workout use icu_download_workout.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    fmt = file_format.lower().lstrip(".")
    if fmt not in {"zwo", "mrc", "erg", "fit"}:
        return ResponseBuilder.build_error_response(
            "file_format must be one of: zwo, mrc, erg, fit", error_type="validation_error"
        )

    try:
        workout_data = json.loads(workout_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON: {str(e)}", error_type="validation_error"
        )
    if not isinstance(workout_data, dict):
        return ResponseBuilder.build_error_response(
            "Workout payload must be a JSON object", error_type="validation_error"
        )

    workout_dict = cast(dict[str, Any], workout_data)
    try:
        async with ICUClient(config) as client:
            content = await client.download_workout_global(workout_dict, f".{fmt}")
            return download_and_respond(
                "workout", content, output_path, "download_workout_global", fmt.upper()
            )
    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )
