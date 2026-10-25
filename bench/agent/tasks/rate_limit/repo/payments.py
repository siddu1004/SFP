"""A tiny payments API. handle(request) returns a response; both are dicts."""
import time


def charge(client_id, amount):
    return {"status": 200, "body": {"charged": amount, "client": client_id}, "headers": {}}


def handle(request, now=None):
    """request: {"client": str, "path": "/charge", "amount": int}."""
    if request.get("path") != "/charge":
        return {"status": 404, "body": {"error": "not found"}, "headers": {}}
    return charge(request["client"], request["amount"])
