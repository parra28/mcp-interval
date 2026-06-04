"""High-level training-plan creation tool.

Creates a folder of type PLAN and bulk-uploads all its workouts and notes in
one call — mirroring the manual upload script flow:

1. Create the plan folder.
2. For every item, compute the relative `day` from the plan's base date.
3. NOTE items get `type="NOTE"` and their `distance` (phase length in days)
   is mapped to the API's `days` field.
4. Attach `folder_id` and bulk-create everything.

Required fields per item: `category` ("WORKOUT" or "NOTE"), `start_date_local`,
and `name`. Missing data is reported back so the caller can supply it.
"""

import json
from datetime import datetime
from typing import Annotated, Any, cast

from fastmcp import Context

from ..auth import ICUConfig
from ..client import ICUAPIError, ICUClient
from ..response_builder import ResponseBuilder

REQUIRED_ITEM_FIELDS = ("category", "start_date_local", "name")
VALID_CATEGORIES = {"WORKOUT", "NOTE"}


def _day_number(start_date_local: str, base_date: str) -> int:
    """Whole days between an item's date and the plan base date (clamped ≥ 0)."""
    item_day = datetime.fromisoformat(start_date_local.split("T")[0])
    base = datetime.fromisoformat(base_date.split("T")[0])
    return max(0, (item_day - base).days)


def _validate_items(items: list[Any]) -> list[str]:
    """Return a list of human-readable problems; empty list means all valid."""
    problems: list[str] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"Item {idx}: must be a JSON object")
            continue
        item_dict = cast(dict[str, Any], item)
        for field in REQUIRED_ITEM_FIELDS:
            if not item_dict.get(field):
                problems.append(f"Item {idx} ('{item_dict.get('name', '?')}'): missing '{field}'")
        category = item_dict.get("category")
        if category and category not in VALID_CATEGORIES:
            problems.append(
                f"Item {idx}: category '{category}' invalid (use WORKOUT or NOTE)"
            )
    return problems


async def create_training_plan(
    plan_name: Annotated[str, "Name of the training plan (folder) to create"],
    items_json: Annotated[
        str,
        "JSON array of plan items. Each needs category ('WORKOUT'|'NOTE'), "
        "start_date_local (ISO) and name. WORKOUTs also take type + description "
        "(workout DSL); NOTEs may include distance = phase length in days.",
    ],
    plan_description: Annotated[str | None, "Optional description for the plan folder"] = None,
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Create a complete training plan in ONE call: a PLAN folder plus all its workouts and notes.

    Bulk-uploads every item, computing each item's `day` offset from the plan's
    earliest date and mapping NOTE `distance` (phase length) to the API `days`
    field. If required data is missing it is reported back instead of uploading
    a partial plan. To add items to an existing folder use icu_create_multiple_workouts.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    # --- Validate the plan name --------------------------------------------
    if not plan_name or not plan_name.strip():
        return ResponseBuilder.build_error_response(
            "Plan name is required. Please provide a name for the plan.",
            error_type="validation_error",
        )

    # --- Parse + validate the items ----------------------------------------
    try:
        parsed = json.loads(items_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON in items: {str(e)}", error_type="validation_error"
        )
    if not isinstance(parsed, list):
        return ResponseBuilder.build_error_response(
            "Items must be a JSON array of plan items.", error_type="validation_error"
        )
    items = cast(list[Any], parsed)
    if not items:
        return ResponseBuilder.build_error_response(
            "The plan has no items. Provide at least one WORKOUT or NOTE.",
            error_type="validation_error",
        )

    problems = _validate_items(items)
    if problems:
        return ResponseBuilder.build_error_response(
            "Some plan items are missing required data. Please complete them and retry.",
            error_type="validation_error",
            suggestions=problems[:50],
        )

    # --- Determine the plan base date (earliest start_date_local) ----------
    dated_items = [cast(dict[str, Any], i) for i in items if cast(dict[str, Any], i).get("start_date_local")]
    base_date = min(i["start_date_local"] for i in dated_items)

    # --- Build the bulk payload --------------------------------------------
    workout_count = 0
    note_count = 0

    try:
        async with ICUClient(config) as client:
            # 1. Create the plan folder
            folder_payload: dict[str, Any] = {
                "name": plan_name,
                "type": "PLAN",
                "description": plan_description or f"Plan created via MCP: {plan_name}",
            }
            folder = await client.create_folder(folder_payload, athlete_id=athlete_id)
            folder_id = folder.id

            # 2. Transform every item
            payload: list[dict[str, Any]] = []
            for raw in items:
                item = dict(cast(dict[str, Any], raw))
                category = item.pop("category", None)

                if category == "NOTE":
                    item["type"] = "NOTE"
                    if "distance" in item:
                        item["days"] = item.pop("distance")
                    note_count += 1
                else:
                    workout_count += 1

                start = item.get("start_date_local")
                if isinstance(start, str):
                    item["day"] = _day_number(start, base_date)

                item["folder_id"] = folder_id
                payload.append(item)

            # 3. Bulk create
            created = await client.create_multiple_workouts(payload, athlete_id=athlete_id)
            succeeded = sum(1 for r in created if isinstance(r, dict) and r.get("id"))

            return ResponseBuilder.build_response(
                data={
                    "plan_name": plan_name,
                    "folder_id": folder_id,
                    "base_date": base_date,
                    "total_items": len(payload),
                    "workouts": workout_count,
                    "notes": note_count,
                    "created": succeeded,
                    "failed": len(payload) - succeeded,
                },
                query_type="create_training_plan",
                metadata={
                    "message": f"Created plan '{plan_name}' (folder {folder_id}) "
                    f"with {succeeded}/{len(payload)} items"
                },
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )
