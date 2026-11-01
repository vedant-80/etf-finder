"""The verdict's shape, shared by every check."""

MOST = 5  # entries a failure message names


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def constraint(identifier, text, ok, expected=None, actual=None, message=""):
    """One named check: ok is True (holds), False (fails) or None (skipped, an earlier check failed)."""
    return {"id": identifier, "constraint": text, "ok": ok, "expected": expected, "actual": actual, "message": message}


def first_failure(constraints):
    failing = [entry for entry in constraints if entry["ok"] is False]
    if not failing:
        return None
    more = f" ({len(failing) - 1} more check(s) fail)" if len(failing) > 1 else ""
    return f"{failing[0]['id']}: {failing[0]['message']}{more}"


def named(items):
    """A short list for a message: the first MOST items, and how many more."""
    items = list(items)
    shown = ", ".join(items[:MOST])
    return shown + (f" and {len(items) - MOST} more" if len(items) > MOST else "")
