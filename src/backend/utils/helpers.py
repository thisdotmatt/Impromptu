import json


def formatSSEMessage(event) -> str:
    return f"data: {json.dumps(event)}\n\n"
