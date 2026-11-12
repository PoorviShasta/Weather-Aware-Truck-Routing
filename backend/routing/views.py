import json
from datetime import datetime, timedelta, timezone

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import planner, providers


class ValidationError(ValueError):
    pass


def _coord(obj, name):
    try:
        lat, lng = float(obj["lat"]), float(obj["lng"])
    except (KeyError, TypeError, ValueError):
        raise ValidationError(f"'{name}' needs numeric lat and lng.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValidationError(f"'{name}' coordinates are out of range.")
    return lat, lng


def parse_plan_request(body):
    origin = _coord(body.get("origin") or {}, "origin")
    destination = _coord(body.get("destination") or {}, "destination")

    try:
        departure = datetime.fromisoformat(str(body["departure"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        raise ValidationError("'departure' must be an ISO-8601 date/time.")
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)
    departure = departure.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if departure > now + timedelta(days=12):
        raise ValidationError("Departure must be within the next 12 days (forecast limit).")
    if departure < now - timedelta(days=2):
        raise ValidationError("Departure cannot be more than 2 days in the past.")

    try:
        load_lb = float(body["load_lb"])
    except (KeyError, TypeError, ValueError):
        raise ValidationError("'load_lb' must be a number.")
    if not (0 <= load_lb <= 80_000):
        raise ValidationError("Load must be between 0 and 80,000 lb.")

    interval = body.get("interval_miles")
    if interval in ("", "auto", None):
        interval = None
    else:
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            raise ValidationError("'interval_miles' must be 10, 25, 50 or auto.")
        if interval not in (10, 25, 50):
            raise ValidationError("'interval_miles' must be 10, 25, 50 or auto.")
    return origin, destination, departure, load_lb, interval


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def geocode(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 3:
        return JsonResponse({"results": []})
    try:
        return JsonResponse({"results": providers.geocode(q)})
    except providers.UpstreamError as exc:
        return JsonResponse({"error": str(exc)}, status=502)


@csrf_exempt
@require_POST
def plan_routes(request):
    try:
        body = json.loads(request.body or b"{}")
        origin, destination, departure, load_lb, interval = parse_plan_request(body)
        result = planner.plan(origin, destination, departure, load_lb, interval)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be JSON."}, status=400)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except providers.UpstreamError as exc:
        return JsonResponse({"error": f"Upstream service problem: {exc}"}, status=502)
    return JsonResponse(result)
