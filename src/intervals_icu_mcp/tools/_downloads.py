"""Shared helper for tools that download binary files (activities, workouts).

Saves the bytes to `output_path` when given, otherwise returns the content
base64-encoded in the JSON response.
"""

import base64
import os
from typing import Any

from ..response_builder import ResponseBuilder


def download_and_respond(
    resource_id: str,
    file_content: bytes,
    output_path: str | None,
    query_type: str,
    format_name: str | None = None,
) -> str:
    """Persist or base64-encode a downloaded file and build the JSON response."""
    try:
        if output_path:
            os.makedirs(
                os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
                exist_ok=True,
            )
            with open(output_path, "wb") as f:
                f.write(file_content)

            data: dict[str, Any] = {
                "resource_id": resource_id,
                "saved_to": output_path,
                "size_bytes": len(file_content),
            }
            if format_name:
                data["format"] = format_name

            return ResponseBuilder.build_response(
                data=data,
                query_type=query_type,
                metadata={"message": f"{format_name or 'File'} saved to {output_path}"},
            )

        encoded = base64.b64encode(file_content).decode("utf-8")
        data = {
            "resource_id": resource_id,
            "size_bytes": len(file_content),
            "content_base64": encoded,
            "note": f"File content is base64 encoded. Decode to get {format_name or 'original'} file.",
        }
        if format_name:
            data["format"] = format_name

        return ResponseBuilder.build_response(data=data, query_type=query_type)
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error saving file: {str(e)}", error_type="internal_error"
        )
