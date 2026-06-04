# Tool, Resource, and Prompt Reference

Complete inventory of everything the Intervals.icu MCP server exposes: up to 83 tools across 12 categories, 4 MCP Resources, and 7 MCP Prompts.

## Delete Safety Mode

Destructive tools are gated by the optional `INTERVALS_ICU_DELETE_MODE` env var. The gate sits **outside the model's reach** — tools that aren't registered cannot be invoked by any prompt or parameter.

| Mode | Registered tools | Events | Activities | Gear | Workouts | Sport settings | Custom items |
|---|---|---|---|---|---|---|---|
| `safe` (default) | 80 | tomorrow or later | ✗ | ✓ | ✓ | ✗ | ✗ |
| `full` | 83 | any date | ✓ | ✓ | ✓ | ✓ | ✓ |
| `none` | 76 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

In `safe` mode, `icu_delete_event` and `icu_bulk_delete_events` return a uniform envelope showing what was deleted and what was skipped:

```json
{
  "deleted": [124],
  "deleted_count": 1,
  "skipped": [
    {
      "id": 123,
      "reason": "past_event",
      "start_date_local": "2026-04-15",
      "hint": "Past events (today and earlier) require INTERVALS_ICU_DELETE_MODE=full."
    }
  ],
  "skipped_count": 1
}
```

Set the mode in your client config alongside the credentials:

```json
"env": {
  "INTERVALS_ICU_API_KEY": "your-api-key-here",
  "INTERVALS_ICU_ATHLETE_ID": "i123456",
  "INTERVALS_ICU_DELETE_MODE": "safe"
}
```

**Events vs. activities — two separate records:** An event is a calendar entry (planned workout, race, note). An activity is a recorded workout synced from a device or uploaded manually. Completing a workout links the activity to the event, but both records remain independent — deleting one leaves the other intact. Deleting an event removes the plan from your calendar; the recorded data survives. Deleting an activity permanently removes the training data; the event remains on the calendar (reverting to an unexecuted plan). This is why `icu_delete_activity` is `full`-only: it destroys recorded training data with no recovery path. Event deletion is available in `safe` mode (future events only) because removing an unexecuted plan is low-stakes.

**Why today is treated as past:** Safe mode only deletes events dated *strictly after today* in the server's local timezone. The one-day buffer absorbs server-vs-athlete TZ skew. If you run the server in Docker (defaults to UTC) and live in a different timezone, set the container's `TZ` env var to match your athlete profile (e.g., `TZ=Europe/Berlin`) so "today" lines up.

**Why sport settings and custom items are full-only:** Sport-settings deletion shifts retroactive chart math (current FTP/zones drive past activity calculations on Intervals.icu, so deleting them re-renders historical training load). Custom items can be data-bearing fields whose values are stored across activities. Neither is recoverable by re-creating the deleted record.

## Tools

### Activities (12 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_recent_activities` | List recent activities with summary metrics | Paginated list of activities with id, name, type, date, distance, moving time, elevation gain, avg/normalized power, avg HR, cadence, training load, and intensity factor |
| `icu_get_activity_details` | Get comprehensive details for a specific activity | Full object with 16 sections: `duration_distance`, `speed_pace`, `power`, `heart_rate`, `cadence`, `training`, `power_model`, `zones`, `altitude`, `weather`, `nutrition`, `subjective`, `equipment`, `flags`, `achievements`, and `analysis_meta` — covers all 100+ API fields |
| `icu_search_activities` | Search activities by name or tag | Lightweight list with id, name, type, date, distance and moving time only; no performance metrics — use `icu_search_activities_full` when watts or training load are needed |
| `icu_search_activities_full` | Search activities with full details | Full list including avg/normalized power, avg HR, cadence, training load, and intensity factor per result |
| `icu_get_activities_around` | Get activities before and after a specific one | Chronologically sorted list with relative position (`before`/`after`/`is_reference`), days offset, distance, moving time, and basic performance metrics |
| `icu_update_activity` | Update activity name, description, or metadata | Updated activity with the modified fields (id, name, type, date, description, trainer, commute, feel, rpe) |
| `icu_delete_activity` | Delete an activity *(only registered when `INTERVALS_ICU_DELETE_MODE=full`)* | Confirmation object with `activity_id` and `deleted: true` |
| `icu_download_activity_file` | Download original activity file | Original device file (FIT/TCX/GPX) saved to disk or base64-encoded with its size in bytes |
| `icu_download_fit_file` | Download activity as FIT file | Activity converted to FIT format, saved to disk or returned as base64 |
| `icu_download_gpx_file` | Download activity as GPX file | Activity converted to GPX format, saved to disk or returned as base64 |
| `icu_bulk_create_manual_activities` | Create multiple manual activities with upsert on external_id | List of created/updated activities with id, name, type, and date for each |
| `icu_update_activity_streams` | Update raw timeseries streams for an activity (JSON or CSV) | Operation confirmation with the raw response returned by the API |

### Activity Analysis (17 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_activity_streams` | Get time-series data (power, HR, cadence, altitude, GPS) | Second-by-second array of data points with the requested channels (power, HR, cadence, altitude, speed, lat/lon, temperature, etc.) |
| `icu_get_activity_intervals` | Get structured workout intervals with targets and performance | List of intervals/laps with per-segment metrics: duration, distance, avg/max/NP power, avg/max HR, cadence, elevation gain, speed, and type (WORK/RECOVERY) |
| `icu_get_best_efforts` | Find peak performances across all durations in an activity | Best-effort table by duration (5s, 1min, 5min, 20min, 1h…) with watts, pace, or HR depending on sport |
| `icu_search_intervals` | Find similar intervals across activity history | Matching intervals from multiple activities with performance metrics and a reference to the source activity |
| `icu_get_power_histogram` | Get power distribution histogram for an activity | Array of buckets `{power_range: {min_watts, max_watts}, time_seconds}` showing how long was spent in each power band |
| `icu_get_hr_histogram` | Get heart rate distribution histogram for an activity | Array of buckets `{hr_range: {min_bpm, max_bpm}, time_seconds}` showing time distribution by heart rate |
| `icu_get_pace_histogram` | Get pace distribution histogram for an activity | Array of buckets `{pace_range: {min, max}, time_seconds}` showing time distribution by pace (sec/km or sec/100m) |
| `icu_get_gap_histogram` | Get grade-adjusted pace histogram for an activity | Array of buckets with grade-adjusted pace (GAP) showing the flat-equivalent effort per time band |
| `icu_get_activity_time_at_hr` | Get time-at-heart-rate distribution for one activity | Raw time-at-HR payload showing how long was spent at each HR / zone in that session |
| `icu_get_activity_weather_summary` | Get the weather summary for one activity (optional sub-range) | Weather object with temperature, wind, clouds, precipitation and feels-like for the activity or an index range |
| `icu_get_activity_hr_load_model` | Get the HR training-load model for one activity | Model object describing how the HR-based load (HRSS/TRIMP) was computed for that session |
| `icu_get_activity_power_spike_model` | Get the power-spike detection model for one activity | Model object flagging implausible power spikes / dropouts in the activity data |
| `icu_get_activity_power_vs_hr` | Get power-vs-HR data points for one activity | Paired power/HR samples for cardiac-drift and aerobic-efficiency analysis within the session |
| `icu_get_activity_hr_curve` | Get the HR curve for one activity | Best sustained HR by duration within that single activity |
| `icu_get_activity_pace_curve` | Get the pace curve for one activity (optional GAP) | Best sustained pace by duration within that activity, raw or grade-adjusted |
| `icu_get_activity_power_curve` | Get the power curve for one activity | Best sustained watts by duration within that single activity |
| `icu_get_activity_power_curves` | Get multiple power curves (several streams) for one activity | Per-stream power curves for the activity in a single response |

### Activity Messages (2 tools)

The threaded notes/comments shown under an activity — the user's own training notes, comments from followers, or coach feedback.

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_activity_messages` | Read notes/comments/coach feedback on a specific activity | List of messages with id, author, text, creation date, and type (own note / comment / coach feedback) |
| `icu_add_activity_message` | Post a note or comment on a specific activity | Created message with its id, text, author, and timestamp |

### Athlete (2 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_athlete_profile` | Get athlete profile with fitness metrics and sport settings | Full profile with name, age, weight, gender, country, configured sports, FTP/FTHR/threshold pace per sport, and current fitness metrics |
| `icu_get_fitness_summary` | Get detailed CTL/ATL/TSB analysis with training recommendations | Current CTL (fitness), ATL (fatigue), and TSB (form) overall and per sport, with 7/42-day trend and recommended load for the next week |

### Wellness (3 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_wellness_data` | Get recent wellness metrics with trends (HRV, sleep, mood, fatigue) | Daily list with HRV (ms and score), resting HR, sleep (duration and quality), weight, SPO2, mood, fatigue, soreness, motivation, active injury flag, and notes |
| `icu_get_wellness_for_date` | Get complete wellness data for a specific date | Single-day record with all wellness indicators and personal baseline values (HRV baseline, resting HR baseline) |
| `icu_update_wellness` | Update or create wellness data for a date | Updated or created wellness record with all submitted fields and date confirmation |

### Events / Calendar (10 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_calendar_events` | Get planned events and workouts from calendar | List of events in the period with id, type, name, date, description, workout structure (if any), and target metrics (TSS, IF, distance, duration) |
| `icu_get_upcoming_workouts` | Get upcoming planned workouts only | List of planned workouts with name, date, description, workout code (DSL), target TSS/IF, and sport |
| `icu_get_event` | Get details for a specific event | Full event with id, type, name, date, description, internal workout structure, target metrics, and execution status (completed/pending) |
| `icu_create_event` | Create new calendar events (workouts, races, notes, goals) | Created event with its id and all registered fields |
| `icu_update_event` | Modify existing calendar events | Updated event with the new values of the modified fields |
| `icu_delete_event` | Remove an event from the calendar *(safe mode: future events only; envelope returns `deleted` / `skipped`)* | Object `{deleted: [ids], deleted_count, skipped: [{id, reason, hint}], skipped_count}` |
| `icu_bulk_create_events` | Create multiple events in a single operation | List of created events with id and date for each |
| `icu_bulk_delete_events` | Delete multiple events in a single operation *(safe mode partitions into `deleted` / `skipped`)* | Object `{deleted: [ids], deleted_count, skipped: [{id, reason, hint}], skipped_count}` |
| `icu_duplicate_events` | Duplicate one or more events with configurable copies and spacing | List of duplicated events with original id, new id, and assigned date |
| `icu_apply_training_plan` | Apply an entire training plan (workout folder) onto the calendar | Confirmation with the number of events created and the date range of the applied plan |

### Performance / Curves (5 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_power_curves` | Analyze power curves with FTP estimation and power zones | Mean maximal power curve by duration (1s→60min+) with watts and W/kg per point, estimated FTP, and derived power zone table |
| `icu_get_hr_curves` | Analyze heart rate curves with HR zones | Maximum sustained HR curve by duration with bpm per point and derived HR zone table |
| `icu_get_pace_curves` | Analyze running/swimming pace curves with optional GAP | Best pace curve by duration in sec/km or sec/100m, with and without grade adjustment (GAP) where applicable |
| `icu_get_power_hr_curve` | Get the athlete's power-vs-HR curve over a date range | Paired power/HR data across the range for cross-session aerobic-efficiency / decoupling trends |
| `icu_get_mmp_model` | Get the Mean Maximal Power model for %MMP workout steps | MMP model parameters used to resolve %MMP targets in workouts to watts for the given sport |

### Workout Library (4 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_workout_library` | Browse workout folders and training plans | Root folder tree with id, name, workout count, and subfolders |
| `icu_get_workouts_in_folder` | View all workouts in a specific folder | List of workouts in the folder with id, name, description, sport, estimated duration, target TSS, and workout DSL code |
| `icu_create_folder` | Create a new workout folder or training plan | Created folder/plan with its id and fields (name, plan scheduling fields when applicable) |
| `icu_update_folder` | Update an existing workout folder or training plan | Updated folder/plan with the new values of the modified fields |

### Workout Management (12 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_list_workouts` | List every workout in the athlete's library | Flat list of all workouts with id, name, type, folder, duration, training load and intensity |
| `icu_get_workout` | Fetch one library workout by ID | Full workout object with id, name, type, folder, and metrics |
| `icu_create_workout` | Create one new workout in a folder/plan | Created workout with its id and fields (structure supplied via the workout DSL in `description`) |
| `icu_create_multiple_workouts` | Create many workouts in a single request | List of created workouts with id and metadata for each |
| `icu_update_workout` | Update an existing library workout | Updated workout with the new values of the modified fields |
| `icu_delete_workout` | Delete a workout from the library *(safe/full only)* | Confirmation with `workout_id`, `deleted: true`, and whether siblings were removed |
| `icu_duplicate_workouts` | Duplicate workouts on a plan | API result describing the duplicated workouts |
| `icu_import_workout` | Import a workout from a .zwo/.mrc/.erg/.fit file into a folder | API result for the imported workout (id, name) and target folder |
| `icu_download_workouts_zip` | Download planned workouts in a date range as a .zip | The .zip saved to disk or returned base64-encoded with its size |
| `icu_download_workout` | Convert one library/athlete workout to a device file | The .zwo/.mrc/.erg/.fit file saved to disk or returned base64-encoded |
| `icu_download_event_workout` | Download a planned (calendar) workout as a device file | The .zwo/.mrc/.erg/.fit file for the event, saved to disk or base64-encoded |
| `icu_download_workout_global` | Convert an arbitrary workout payload to a file (no athlete context) | The converted file saved to disk or returned base64-encoded |

### Gear Management (6 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_gear_list` | Get all gear items with usage and status | List of gear items with id, name, type, cumulative distance, hours of use, start date, active/retired status, and pending maintenance reminders |
| `icu_create_gear` | Add new gear to tracking | Created gear item with its id and all registered fields |
| `icu_update_gear` | Update gear details, mileage, or status | Updated gear item with the new values of the modified fields |
| `icu_delete_gear` | Remove gear from tracking | Confirmation with `gear_id` and `deleted: true` |
| `icu_create_gear_reminder` | Create maintenance reminders for gear | Created reminder with id, name, distance/time threshold, and current status |
| `icu_update_gear_reminder` | Update existing gear maintenance reminders | Updated reminder with the new threshold values and status |

### Sport Settings (5 tools)

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_sport_settings` | Get sport-specific settings and thresholds | Sport configuration with FTP, LTHR, threshold pace, W', power zones (W), HR zones (bpm), and pace zones (sec/km) |
| `icu_update_sport_settings` | Update FTP, FTHR, pace threshold, or zone configuration | Updated sport configuration with all thresholds and recalculated zones |
| `icu_apply_sport_settings` | Apply updated settings to historical activities | Confirmation of how many historical activities were re-analysed with the new configuration |
| `icu_create_sport_settings` | Create new sport-specific settings | Newly created sport configuration with its type and all established thresholds |
| `icu_delete_sport_settings` | Delete sport-specific settings *(only registered when `INTERVALS_ICU_DELETE_MODE=full`; deletion shifts retroactive chart math)* | Deletion confirmation with a warning about the impact on historical calculations |

### Custom Items (5 tools)

The user's personal additions to their account: custom charts on dashboards, custom data fields on wellness/activities/intervals, custom power/HR/pace zone configurations, custom activity panels, and custom computed streams. The Intervals.icu API umbrella name is "custom items".

| Tool | Description | Result |
| ---- | ----------- | ------ |
| `icu_get_custom_items` | List the user's custom additions (charts, fields, zones, panels, etc.) | List of custom items with id, name, type (`CHART`, `INPUT_FIELD`, `ACTIVITY_FIELD`, `ZONE_CONFIG`, etc.), and visibility |
| `icu_get_custom_item` | Fetch the full configuration of one custom addition by ID | Full item configuration with id, name, type, and a `content` object containing all type-specific parameters |
| `icu_create_custom_item` | Add a new custom chart, field, zones config, or dashboard panel | Created custom item with its id and full configuration |
| `icu_update_custom_item` | Modify an existing custom addition (rename, reconfigure, change visibility) | Updated item with the new configuration values |
| `icu_delete_custom_item` | Permanently remove a custom addition *(only registered when `INTERVALS_ICU_DELETE_MODE=full`; data-bearing field types may cascade)* | Deletion confirmation with the id of the removed item |

## MCP Resources

Resources provide ongoing context to the LLM without requiring explicit tool calls.

| Resource                              | Description                                                              |
| ------------------------------------- | ------------------------------------------------------------------------ |
| `intervals-icu://athlete/profile`     | Complete athlete profile with current fitness metrics and sport settings |
| `intervals-icu://workout-syntax`      | Structured workout syntax reference for generating valid Intervals.icu workouts (cycling, running, swimming) |
| `intervals-icu://event-categories`    | Calendar event category enum (WORKOUT, RACE_A/B/C, HOLIDAY, …), training_availability values, legacy aliases, and use-case guidance for create_event / update_event / bulk_create_events |
| `intervals-icu://custom-item-schemas` | Per-item_type `content` schema for create_custom_item / update_custom_item — INPUT_FIELD/ACTIVITY_FIELD/INTERVAL_FIELD constraints with worked examples; chart/panel/zones/stream guidance |

## MCP Prompts

Prompt templates for common queries, accessible via prompt suggestions in Claude.

| Prompt                    | Description                                                              |
| ------------------------- | ------------------------------------------------------------------------ |
| `icu_analyze_recent_training` | Comprehensive training analysis over a specified period                  |
| `icu_performance_analysis`    | Detailed power/HR/pace curve analysis with zones                         |
| `icu_activity_deep_dive`      | Deep dive into a specific activity with streams, intervals, best efforts |
| `icu_recovery_check`          | Recovery assessment with wellness trends and training load               |
| `icu_training_plan_review`    | Weekly training plan evaluation with workout library                     |
| `icu_plan_training_week`      | AI-assisted weekly training plan creation based on current fitness       |
| `generate_workout`            | Generate a structured workout with sport, type, and duration parameters  |
