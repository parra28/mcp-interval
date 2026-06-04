"""Activity-related tools for Intervals.icu MCP server."""

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastmcp import Context

from ..auth import ICUConfig
from ..client import ICUAPIError, ICUClient
from ..response_builder import ResponseBuilder
from ._strava import strava_limitation_note


async def get_recent_activities(
    limit: Annotated[int, "Number of activities to fetch"] = 30,
    days_back: Annotated[int, "Number of days to look back"] = 30,
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """List the athlete's most recent activities (default last 30 days) — LIGHT summary per item (distance, duration, power, HR, training load).

    Use for "what have I done recently?", "show last week's rides". For
    one specific activity by ID use icu_get_activity_details; to search by
    name/tag use icu_search_activities.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        # Calculate date range
        oldest_date = datetime.now() - timedelta(days=days_back)
        oldest = oldest_date.strftime("%Y-%m-%d")

        async with ICUClient(config) as client:
            activities = await client.get_activities(
                athlete_id=athlete_id,
                oldest=oldest,
                limit=min(limit, 100),  # Cap at 100
            )

            if not activities:
                return ResponseBuilder.build_response(
                    data={"activities": [], "count": 0},
                    metadata={"message": "No activities found"},
                )

            activities_data: list[dict[str, Any]] = []
            for activity in activities:
                activity_item: dict[str, Any] = {
                    "id": activity.id,
                    "name": activity.name or "Untitled",
                    "start_date": activity.start_date_local,
                    "type": activity.type,
                }

                if activity.distance:
                    activity_item["distance_meters"] = activity.distance

                if activity.moving_time:
                    activity_item["moving_time_seconds"] = activity.moving_time

                if activity.total_elevation_gain:
                    activity_item["elevation_gain_meters"] = activity.total_elevation_gain

                # Performance metrics
                if activity.average_watts:
                    activity_item["average_watts"] = activity.average_watts
                if activity.normalized_power:
                    activity_item["normalized_power"] = activity.normalized_power
                if activity.average_heartrate:
                    activity_item["average_heartrate"] = activity.average_heartrate
                if activity.average_cadence:
                    activity_item["average_cadence"] = activity.average_cadence

                # Training load
                if activity.icu_training_load:
                    activity_item["training_load"] = activity.icu_training_load
                if activity.icu_intensity:
                    activity_item["intensity_factor"] = activity.icu_intensity

                activities_data.append(activity_item)

            return ResponseBuilder.build_response(
                data={"activities": activities_data, "count": len(activities_data)},
                query_type="recent_activities",
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def get_activity_details(
    activity_id: Annotated[str, "Activity ID to fetch"],
    ctx: Context | None = None,
) -> str:
    """Fetch the headline SUMMARY of one activity — name, sport, date, distance, duration, training load, weather, plus all top-level metrics in a single JSON blob.

    Use for "how was my ride?", "tell me about activity X". For lap-by-lap or
    per-interval breakdown use icu_get_activity_intervals; for second-by-second
    time-series use icu_get_activity_streams.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            activity = await client.get_activity(activity_id=activity_id)

            # Extra fields from the API not explicitly defined in the model
            extra = activity.model_extra or {}

            def _v(name: str) -> Any:
                """Return named model field or fall back to model_extra."""
                val = getattr(activity, name, None)
                return val if val is not None else extra.get(name)

            def _section(**kwargs: Any) -> dict[str, Any]:
                return {k: v for k, v in kwargs.items() if v is not None}

            activity_data: dict[str, Any] = {
                "id": activity.id,
                "name": activity.name or "Untitled",
                "type": activity.type,
                "start_date": activity.start_date_local,
            }

            if activity.description:
                activity_data["description"] = activity.description

            tags = _v("tags")
            if tags:
                activity_data["tags"] = tags

            source = _v("source")
            if source:
                activity_data["source"] = source

            strava_id = _v("strava_id")
            if strava_id:
                activity_data["strava_id"] = strava_id

            icu_color = _v("icu_color")
            if icu_color:
                activity_data["icu_color"] = icu_color

            # Duration & distance
            duration = _section(
                moving_time_seconds=activity.moving_time,
                elapsed_time_seconds=activity.elapsed_time,
                recording_time_seconds=_v("icu_recording_time"),
                coasting_time_seconds=_v("coasting_time"),
                distance_meters=activity.distance,
                icu_distance_meters=_v("icu_distance"),
                elevation_gain_meters=activity.total_elevation_gain,
                elevation_loss_meters=_v("total_elevation_loss"),
                lengths=_v("lengths"),
                pool_length_meters=_v("pool_length"),
            )
            if duration:
                activity_data["duration_distance"] = duration

            # Speed & pace
            speed_pace = _section(
                average_speed_mps=activity.average_speed,
                max_speed_mps=activity.max_speed,
                gap_mps=_v("gap"),
                gap_model=_v("gap_model"),
                pace=_v("pace"),
                threshold_pace=_v("threshold_pace"),
                average_stride=_v("average_stride"),
            )
            if speed_pace:
                activity_data["speed_pace"] = speed_pace

            # Power metrics
            power_metrics: dict[str, Any] = {}
            if activity.average_watts:
                power_metrics["average"] = activity.average_watts
            if _v("normalized_power"):
                power_metrics["normalized"] = _v("normalized_power")
            if activity.weighted_average_watts:
                power_metrics["weighted_average"] = activity.weighted_average_watts
            if activity.max_watts:
                power_metrics["max"] = activity.max_watts
            if activity.variability_index:
                power_metrics["variability_index"] = round(activity.variability_index, 2)
            if activity.efficiency_factor:
                power_metrics["efficiency_factor"] = round(activity.efficiency_factor, 2)
            for key in (
                "icu_power_hr", "icu_joules", "icu_joules_above_ftp",
                "icu_max_wbal_depletion", "decoupling", "polarization_index",
                "strain_score", "p30s_exponent",
            ):
                val = _v(key)
                if val is not None:
                    power_metrics[key] = val
            if _v("device_watts") is not None:
                power_metrics["device_watts"] = _v("device_watts")
            if power_metrics:
                activity_data["power"] = power_metrics

            # Heart rate
            hr_metrics: dict[str, Any] = {}
            if activity.average_heartrate:
                hr_metrics["average"] = activity.average_heartrate
            if activity.max_heartrate:
                hr_metrics["max"] = activity.max_heartrate
            for key in ("lthr", "icu_resting_hr", "athlete_max_hr"):
                val = _v(key)
                if val is not None:
                    hr_metrics[key] = val
            if _v("has_heartrate") is not None:
                hr_metrics["has_heartrate"] = _v("has_heartrate")
            if _v("icu_ignore_hr") is not None:
                hr_metrics["icu_ignore_hr"] = _v("icu_ignore_hr")
            hrr = _v("icu_hrr")
            if hrr:
                hr_metrics["hrr"] = hrr
            if hr_metrics:
                activity_data["heart_rate"] = hr_metrics

            # Cadence
            cadence_metrics = _section(
                average=activity.average_cadence,
                max=activity.max_cadence,
                icu_cadence_z2=_v("icu_cadence_z2"),
                avg_lr_balance=activity.avg_lr_balance,
            )
            if cadence_metrics:
                activity_data["cadence"] = cadence_metrics

            # Training load
            training_metrics: dict[str, Any] = {}
            if activity.icu_training_load:
                training_metrics["training_load"] = activity.icu_training_load
            if activity.icu_intensity:
                training_metrics["intensity_factor"] = activity.icu_intensity
            if activity.tss:
                training_metrics["tss"] = round(activity.tss, 0)
            if activity.hrss:
                training_metrics["hrss"] = round(activity.hrss, 0)
            if activity.trimp:
                training_metrics["trimp"] = round(activity.trimp, 0)
            for key in (
                "icu_atl", "icu_ctl", "icu_training_load_data",
                "icu_warmup_time", "icu_cooldown_time", "icu_lap_count",
            ):
                val = _v(key)
                if val is not None:
                    training_metrics[key] = val
            if training_metrics:
                activity_data["training"] = training_metrics

            # Power model parameters
            model_params = _section(
                icu_ftp=_v("icu_ftp"),
                icu_w_prime=_v("icu_w_prime"),
                p_max=_v("p_max"),
                icu_pm_cp=_v("icu_pm_cp"),
                icu_pm_w_prime=_v("icu_pm_w_prime"),
                icu_pm_p_max=_v("icu_pm_p_max"),
                icu_pm_ftp=_v("icu_pm_ftp"),
                icu_pm_ftp_secs=_v("icu_pm_ftp_secs"),
                icu_pm_ftp_watts=_v("icu_pm_ftp_watts"),
                icu_rolling_cp=_v("icu_rolling_cp"),
                icu_rolling_w_prime=_v("icu_rolling_w_prime"),
                icu_rolling_p_max=_v("icu_rolling_p_max"),
                icu_rolling_ftp=_v("icu_rolling_ftp"),
                icu_rolling_ftp_delta=_v("icu_rolling_ftp_delta"),
                ss_cp=_v("ss_cp"),
                ss_w_prime=_v("ss_w_prime"),
                ss_p_max=_v("ss_p_max"),
                icu_sweet_spot_min=_v("icu_sweet_spot_min"),
                icu_sweet_spot_max=_v("icu_sweet_spot_max"),
                icu_power_spike_threshold=_v("icu_power_spike_threshold"),
                icu_power_hr_z2=_v("icu_power_hr_z2"),
                icu_power_hr_z2_mins=_v("icu_power_hr_z2_mins"),
                icu_weight_kg=_v("icu_weight"),
            )
            if model_params:
                activity_data["power_model"] = model_params

            # Zones
            zones: dict[str, Any] = {}
            for key in (
                "icu_hr_zones", "icu_hr_zone_times",
                "icu_power_zones", "icu_zone_times",
                "pace_zones", "pace_zone_times",
                "gap_zone_times", "custom_zones", "tiz_order",
            ):
                val = _v(key)
                if val is not None:
                    zones[key] = val
            if zones:
                activity_data["zones"] = zones

            # Altitude
            altitude = _section(
                average=_v("average_altitude"),
                min=_v("min_altitude"),
                max=_v("max_altitude"),
            )
            if altitude:
                activity_data["altitude"] = altitude

            # Weather
            weather: dict[str, Any] = {}
            for key in (
                "average_temp", "min_temp", "max_temp",
                "average_weather_temp", "min_weather_temp", "max_weather_temp",
                "average_feels_like", "min_feels_like", "max_feels_like",
                "average_wind_speed", "average_wind_gust", "prevailing_wind_deg",
                "headwind_percent", "tailwind_percent", "average_clouds",
                "max_rain", "max_snow",
            ):
                val = _v(key)
                if val is not None:
                    weather[key] = val
            if weather:
                activity_data["weather"] = weather

            # Nutrition
            nutrition: dict[str, Any] = {}
            if activity.calories:
                nutrition["calories_burned"] = activity.calories
            if activity.carbs_ingested is not None:
                nutrition["carbs_ingested_g"] = activity.carbs_ingested
            if activity.carbs_used is not None:
                nutrition["carbs_used_g"] = activity.carbs_used
            if nutrition:
                activity_data["nutrition"] = nutrition

            # Subjective
            subjective: dict[str, Any] = {}
            if activity.feel:
                subjective["feel"] = activity.feel
            if activity.perceived_exertion:
                subjective["rpe"] = activity.perceived_exertion
            for key in ("icu_rpe", "session_rpe"):
                val = _v(key)
                if val is not None:
                    subjective[key] = val
            if subjective:
                activity_data["subjective"] = subjective

            # Gear & equipment
            gear_info: dict[str, Any] = {}
            gear = _v("gear")
            if gear:
                gear_info["gear"] = gear
            for key in ("device_name", "power_meter", "power_meter_serial",
                        "power_meter_battery", "crank_length"):
                val = _v(key) or getattr(activity, key, None)
                if val is not None:
                    gear_info[key] = val
            if gear_info:
                activity_data["equipment"] = gear_info

            # Activity flags
            flags: dict[str, Any] = {}
            for attr in ("trainer", "indoor", "commute", "race"):
                val = getattr(activity, attr, None) or _v(attr)
                if val:
                    flags[attr] = val
            for key in ("sub_type", "icu_ignore_time", "icu_ignore_power",
                        "ignore_velocity", "ignore_pace", "use_elevation_correction"):
                val = _v(key)
                if val is not None and val is not False:
                    flags[key] = val
            if flags:
                activity_data["flags"] = flags

            # Achievements & summaries
            achievements_data: dict[str, Any] = {}
            icu_achievements = _v("icu_achievements")
            if icu_achievements:
                achievements_data["icu_achievements"] = icu_achievements
            interval_summary = _v("interval_summary")
            if interval_summary:
                achievements_data["interval_summary"] = interval_summary
            if achievements_data:
                activity_data["achievements"] = achievements_data

            # Stream & analysis metadata
            meta: dict[str, Any] = {}
            for key in ("stream_types", "has_segments", "power_field",
                        "power_field_names", "file_type", "analyzed",
                        "icu_intervals_edited", "lock_intervals", "icu_median_time_delta"):
                val = _v(key) or getattr(activity, key, None)
                if val is not None and val is not False:
                    meta[key] = val
            if meta:
                activity_data["analysis_meta"] = meta

            analysis: dict[str, Any] = {}
            strava_note = strava_limitation_note(activity)
            if strava_note:
                analysis["data_availability"] = strava_note

            metadata: dict[str, Any] = {}
            if activity.feel is not None or activity.perceived_exertion is not None:
                scales = {}
                if activity.feel is not None:
                    scales["feel"] = "1-5"
                if activity.perceived_exertion is not None:
                    scales["rpe"] = "1-10"
                if scales:
                    metadata["subjective_scales"] = scales

            return ResponseBuilder.build_response(
                data=activity_data,
                analysis=analysis if analysis else None,
                metadata=metadata if metadata else None,
                query_type="activity_details",
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def search_activities(
    query: Annotated[str, "Search query (activity name or tag)"],
    limit: Annotated[int, "Maximum number of results to return"] = 30,
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Search activities by name or tag, returning a LIGHT result list — id, name, type, date, distance, time only.

    Use this first for "find my X" queries. Only escalate to
    search_activities_full when you specifically need power, HR, training
    load, or intensity-factor data on the matches (heavier payload).
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    if not query.strip():
        return ResponseBuilder.build_error_response(
            "Search query cannot be empty",
            error_type="validation_error",
        )

    try:
        async with ICUClient(config) as client:
            results = await client.search_activities(
                athlete_id=athlete_id,
                query=query,
                limit=min(limit, 100),  # Cap at 100
            )

            if not results:
                return ResponseBuilder.build_response(
                    data={"activities": [], "count": 0, "query": query},
                    metadata={"message": f"No activities found matching '{query}'"},
                )

            activities_data: list[dict[str, Any]] = []
            for result in results:
                activity_item: dict[str, Any] = {
                    "id": result.id,
                    "name": result.name or "Untitled",
                    "start_date": result.start_date_local,
                    "type": result.type,
                }

                if result.distance:
                    activity_item["distance_meters"] = result.distance

                if result.moving_time:
                    activity_item["moving_time_seconds"] = result.moving_time

                activities_data.append(activity_item)

            return ResponseBuilder.build_response(
                data={"activities": activities_data, "count": len(activities_data), "query": query},
                query_type="search_activities",
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def update_activity(
    activity_id: Annotated[str, "Activity ID to update"],
    name: Annotated[str | None, "Updated activity name"] = None,
    description: Annotated[str | None, "Updated description"] = None,
    activity_type: Annotated[str | None, "Updated activity type (e.g., Ride, Run, Swim)"] = None,
    trainer: Annotated[bool | None, "Mark as trainer/indoor workout"] = None,
    commute: Annotated[bool | None, "Mark as commute"] = None,
    feel: Annotated[int | None, "How you felt (1-5 scale)"] = None,
    perceived_exertion: Annotated[int | None, "RPE rating (1-10 scale)"] = None,
    ctx: Context | None = None,
) -> str:
    """Update an existing activity's metadata (name, type, trainer flag, RPE, feel, etc.).

    Only fields you pass are sent; everything else stays unchanged.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        # Build update data (only include provided fields)
        activity_data: dict[str, Any] = {}

        if name is not None:
            activity_data["name"] = name
        if description is not None:
            activity_data["description"] = description
        if activity_type is not None:
            activity_data["type"] = activity_type
        if trainer is not None:
            activity_data["trainer"] = trainer
        if commute is not None:
            activity_data["commute"] = commute
        if feel is not None:
            activity_data["feel"] = feel
        if perceived_exertion is not None:
            activity_data["perceived_exertion"] = perceived_exertion

        if not activity_data:
            return ResponseBuilder.build_error_response(
                "No fields provided to update. Please specify at least one field to change.",
                error_type="validation_error",
            )

        async with ICUClient(config) as client:
            activity = await client.update_activity(activity_id, activity_data)

            result_data: dict[str, Any] = {
                "id": activity.id,
                "name": activity.name or "Untitled",
                "type": activity.type,
                "start_date": activity.start_date_local,
            }

            if activity.description:
                result_data["description"] = activity.description
            if activity.trainer is not None:
                result_data["trainer"] = activity.trainer
            if activity.commute is not None:
                result_data["commute"] = activity.commute
            if activity.feel is not None:
                result_data["feel"] = activity.feel
            if activity.perceived_exertion is not None:
                result_data["rpe"] = activity.perceived_exertion

            return ResponseBuilder.build_response(
                data=result_data,
                query_type="update_activity",
                metadata={"message": f"Successfully updated activity {activity_id}"},
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def delete_activity(
    activity_id: Annotated[str, "Activity ID to delete"],
    ctx: Context | None = None,
) -> str:
    """Permanently delete an activity. Destructive — cannot be undone. Only registered when INTERVALS_ICU_DELETE_MODE=full."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            success = await client.delete_activity(activity_id)

            if success:
                return ResponseBuilder.build_response(
                    data={"activity_id": activity_id, "deleted": True},
                    query_type="delete_activity",
                    metadata={"message": f"Successfully deleted activity {activity_id}"},
                )
            else:
                return ResponseBuilder.build_error_response(
                    f"Failed to delete activity {activity_id}",
                    error_type="api_error",
                )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


def _download_and_respond(
    activity_id: str,
    file_content: bytes,
    output_path: str | None,
    query_type: str,
    format_name: str | None = None,
) -> str:
    """Helper to process and respond to file downloads."""
    try:
        if output_path:
            # Save to file
            import os

            os.makedirs(
                os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
                exist_ok=True,
            )
            with open(output_path, "wb") as f:
                f.write(file_content)

            data: dict[str, Any] = {
                "activity_id": activity_id,
                "saved_to": output_path,
                "size_bytes": len(file_content),
            }
            if format_name:
                data["format"] = format_name

            return ResponseBuilder.build_response(
                data=data,
                query_type=query_type,
                metadata={"message": f"{format_name or 'Activity'} file saved to {output_path}"},
            )
        else:
            # Return base64 encoded
            import base64

            encoded = base64.b64encode(file_content).decode("utf-8")

            data = {
                "activity_id": activity_id,
                "size_bytes": len(file_content),
                "content_base64": encoded,
                "note": f"File content is base64 encoded. Decode to get {'original' if not format_name else format_name} file.",
            }
            if format_name:
                data["format"] = format_name

            return ResponseBuilder.build_response(
                data=data,
                query_type=query_type,
            )
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error saving file: {str(e)}", error_type="internal_error"
        )


async def download_activity_file(
    activity_id: Annotated[str, "Activity ID to download"],
    output_path: Annotated[str | None, "Path to save the file (optional)"] = None,
    ctx: Context | None = None,
) -> str:
    """Download the original activity file.

    Downloads the ORIGINAL uploaded file (FIT, TCX, or GPX — whatever the
    device produced). Different from download_fit_file (forces FIT conversion)
    and download_gpx_file (forces GPX conversion). If `output_path` is set
    the file is saved there; otherwise the response embeds base64 content.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            file_content = await client.download_activity_file(activity_id)
            return _download_and_respond(
                activity_id, file_content, output_path, "download_activity_file"
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def download_fit_file(
    activity_id: Annotated[str, "Activity ID to download"],
    output_path: Annotated[str | None, "Path to save the FIT file (optional)"] = None,
    ctx: Context | None = None,
) -> str:
    """Download activity converted to FIT format (Garmin / most training platforms). Different from download_activity_file (original upload format) and download_gpx_file (GPX format)."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            file_content = await client.download_fit_file(activity_id)
            return _download_and_respond(
                activity_id, file_content, output_path, "download_fit_file", "FIT"
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def download_gpx_file(
    activity_id: Annotated[str, "Activity ID to download"],
    output_path: Annotated[str | None, "Path to save the GPX file (optional)"] = None,
    ctx: Context | None = None,
) -> str:
    """Download activity converted to GPX format (GPS devices, mapping software). Different from download_activity_file (original upload format) and download_fit_file (FIT format)."""
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            file_content = await client.download_gpx_file(activity_id)
            return _download_and_respond(
                activity_id, file_content, output_path, "download_gpx_file", "GPX"
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def search_activities_full(
    query: Annotated[str, "Search query (activity name or tag)"],
    limit: Annotated[int, "Maximum number of results to return"] = 30,
    ctx: Context | None = None,
) -> str:
    """Search activities by name or tag, returning FULL Activity objects with power, HR, training load, intensity factor, normalized power, weather — every metric per result.

    Heavy payload. Use only when the lighter search_activities won't tell
    you what you need (e.g. "find my threshold rides with NP above 250W").
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    if not query.strip():
        return ResponseBuilder.build_error_response(
            "Search query cannot be empty",
            error_type="validation_error",
        )

    try:
        async with ICUClient(config) as client:
            activities = await client.search_activities_full(
                query=query,
                limit=min(limit, 100),
            )

            if not activities:
                return ResponseBuilder.build_response(
                    data={"activities": [], "count": 0, "query": query},
                    metadata={"message": f"No activities found matching '{query}'"},
                )

            activities_data: list[dict[str, Any]] = []
            for activity in activities:
                activity_item: dict[str, Any] = {
                    "id": activity.id,
                    "name": activity.name or "Untitled",
                    "type": activity.type,
                    "start_date": activity.start_date_local,
                }

                # Basic metrics
                if activity.distance:
                    activity_item["distance_meters"] = activity.distance
                if activity.moving_time:
                    activity_item["moving_time_seconds"] = activity.moving_time
                if activity.total_elevation_gain:
                    activity_item["elevation_gain_meters"] = activity.total_elevation_gain

                # Performance metrics
                performance: dict[str, Any] = {}
                if activity.average_watts:
                    performance["average_watts"] = activity.average_watts
                if activity.normalized_power:
                    performance["normalized_power"] = activity.normalized_power
                if activity.average_heartrate:
                    performance["average_heartrate"] = activity.average_heartrate
                if activity.average_cadence:
                    performance["average_cadence"] = activity.average_cadence
                if performance:
                    activity_item["performance"] = performance

                # Training load
                if activity.icu_training_load:
                    activity_item["training_load"] = activity.icu_training_load
                if activity.icu_intensity:
                    activity_item["intensity_factor"] = activity.icu_intensity

                activities_data.append(activity_item)

            return ResponseBuilder.build_response(
                data={
                    "activities": activities_data,
                    "count": len(activities_data),
                    "query": query,
                },
                query_type="search_activities_full",
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def get_activities_around(
    activity_id: Annotated[str, "Reference activity ID"],
    count: Annotated[int, "Number of activities before and after"] = 5,
    ctx: Context | None = None,
) -> str:
    """Fetch the activities chronologically before and after a reference activity (N each side).

    Use for "what did I do around this race?", training-context queries,
    progression comparisons.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            activities = await client.get_activities_around(
                activity_id=activity_id,
                count=count,
            )

            if not activities:
                return ResponseBuilder.build_response(
                    data={
                        "activities": [],
                        "count": 0,
                        "reference_activity_id": activity_id,
                    },
                    metadata={"message": "No activities found around the reference activity"},
                )

            # Sort by date
            activities.sort(key=lambda x: x.start_date_local)

            # Find the reference activity position
            ref_index = next((i for i, a in enumerate(activities) if a.id == activity_id), None)

            activities_data: list[dict[str, Any]] = []
            for i, activity in enumerate(activities):
                activity_item: dict[str, Any] = {
                    "id": activity.id,
                    "name": activity.name or "Untitled",
                    "type": activity.type,
                    "start_date": activity.start_date_local,
                }

                # Mark if this is the reference activity
                if activity.id == activity_id:
                    activity_item["is_reference"] = True
                elif ref_index is not None:
                    if i < ref_index:
                        activity_item["position"] = "before"
                        activity_item["days_before"] = ref_index - i
                    else:
                        activity_item["position"] = "after"
                        activity_item["days_after"] = i - ref_index

                # Basic metrics
                if activity.distance:
                    activity_item["distance_meters"] = activity.distance
                if activity.moving_time:
                    activity_item["moving_time_seconds"] = activity.moving_time
                if activity.icu_training_load:
                    activity_item["training_load"] = activity.icu_training_load

                # Performance summary
                performance: dict[str, Any] = {}
                if activity.average_watts:
                    performance["average_watts"] = activity.average_watts
                if activity.average_heartrate:
                    performance["average_heartrate"] = activity.average_heartrate
                if performance:
                    activity_item["performance"] = performance

                activities_data.append(activity_item)

            result_data = {
                "reference_activity_id": activity_id,
                "activities": activities_data,
                "count": len(activities_data),
            }

            if ref_index is not None:
                result_data["reference_position"] = ref_index
                result_data["activities_before"] = ref_index
                result_data["activities_after"] = len(activities) - ref_index - 1

            return ResponseBuilder.build_response(
                data=result_data,
                query_type="activities_around",
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def update_activity_streams(
    activity_id: Annotated[str, "Activity ID to update"],
    payload_string: Annotated[str, "JSON array of stream dictionaries or raw CSV data"],
    format: Annotated[str, "Format of the payload: 'json' or 'csv'"] = "json",
    ctx: Context | None = None,
) -> str:
    """Upload raw time-series streams (power, HR, cadence, etc.) onto an existing activity. Destructive — overwrites existing stream data.

    Accepts JSON array or CSV. Different from get_activity_streams (READ).
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    try:
        async with ICUClient(config) as client:
            if format.lower() == "csv":
                response = await client.update_activity_streams_csv(
                    activity_id=activity_id,
                    csv_data=payload_string,
                )
            else:
                import json

                try:
                    streams = json.loads(payload_string)
                except json.JSONDecodeError as e:
                    return ResponseBuilder.build_error_response(
                        f"Invalid JSON payload: {str(e)}",
                        error_type="validation_error",
                    )
                response = await client.update_activity_streams(
                    activity_id=activity_id,
                    streams=streams,
                )

            return ResponseBuilder.build_response(
                data=response,
                query_type="update_activity_streams",
                metadata={"message": f"Successfully updated streams for activity {activity_id}"},
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def bulk_create_manual_activities(
    activities_json: Annotated[str, "JSON string containing array of manual activities"],
    athlete_id: Annotated[str | None, "Athlete ID (for coaches managing multiple athletes)"] = None,
    ctx: Context | None = None,
) -> str:
    """Batch-create manual activities (no device upload) with UPSERT on `external_id`.

    Existing activities with a matching external_id (set by the same
    OAuth app) are updated; activities without an external_id are always
    created new.
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    import json

    try:
        activities = json.loads(activities_json)
    except json.JSONDecodeError as e:
        return ResponseBuilder.build_error_response(
            f"Invalid JSON format: {str(e)}",
            error_type="validation_error",
        )

    if not isinstance(activities, list):
        return ResponseBuilder.build_error_response(
            "Input must be a JSON array of activities",
            error_type="validation_error",
        )

    from typing import Any

    activities_list: list[dict[str, Any]] = activities  # type: ignore[assignment]

    try:
        async with ICUClient(config) as client:
            created_activities = await client.bulk_create_manual_activities(
                athlete_id=athlete_id,
                activities=activities_list,
            )

            activities_data: list[dict[str, Any]] = []
            for result in created_activities:
                activity_item: dict[str, Any] = {
                    "id": result.id,
                    "name": result.name or "Untitled",
                    "start_date": result.start_date_local,
                    "type": result.type,
                }
                activities_data.append(activity_item)

            return ResponseBuilder.build_response(
                data={"activities": activities_data, "count": len(activities_data)},
                query_type="bulk_create_manual_activities",
                metadata={
                    "message": f"Successfully processed {len(activities_data)} manual activities"
                },
            )

    except ICUAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )
