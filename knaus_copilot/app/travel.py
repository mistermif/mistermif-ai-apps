from __future__ import annotations

import csv
import io
import math
import re
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from .memory import MemoryStore


MOVING_KMH = 5.0
STOPPED_KMH = 2.0
START_SAMPLES = 4
START_MIN_DISTANCE_KM = 0.10
DEFAULT_BASE_RADIUS_M = 200
MAX_GPS_ACCURACY_M = 100
MAX_REASONABLE_SPEED_KMH = 140


class TravelTracker:
    """Local GPS trip recorder. It never calls an AI or an external service."""

    def __init__(self, memory: MemoryStore, arrival_minutes: int = 120):
        self.memory = memory
        self.arrival_minutes = arrival_minutes
        self._moving_streak = 0
        self._candidate_location: tuple[float, float] | None = None

    def capture_plan(self, message: str) -> dict[str, Any] | None:
        normalized = " ".join(message.strip().split())
        match = re.search(
            r"\b(?:parto|partiamo|partir[oò]|partiremo|andr[oò]|andremo)\b"
            r".*?\b(?:per|verso)\s+(?:(?:il|lo|la|l')\s+)?(.+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        destination = match.group(1).strip(" .,!?:;-")
        if len(destination) < 3:
            return None
        plan_id = self.memory.add_travel_plan(destination, normalized)
        return {"id": plan_id, "destination": destination, "text": normalized}

    def observe(self, states: list[dict[str, Any]]) -> dict[str, Any]:
        location = self._location(states)
        if location is None:
            return {"status": "gps_unavailable"}
        latitude, longitude = location
        speed = self._metric(states, ("gps", "veloc"), ("speed",)) or 0.0
        accuracy = self._metric(states, ("gps", "accuracy"), ("gps", "precision"))
        if accuracy is not None and accuracy > MAX_GPS_ACCURACY_M:
            self._reset_start_candidate()
            return {"status": "gps_inaccurate", "accuracy_m": accuracy}
        speed = speed if 0 <= speed <= MAX_REASONABLE_SPEED_KMH else 0.0
        now = datetime.now(timezone.utc)
        active = self.memory.active_trip()
        newly_started = False

        if active is None:
            if speed < MOVING_KMH:
                self._reset_start_candidate()
                return {"status": "stationary", "speed_kmh": speed}
            if self._at_base(latitude, longitude):
                # A GPS receiver can report small speeds while the vehicle is parked.
                # Keep the latest point as the departure origin, but require a fresh
                # streak of samples after the vehicle has actually left the geofence.
                self._candidate_location = location
                self._moving_streak = 0
                return {"status": "at_base", "speed_kmh": speed}
            if self._candidate_location is None:
                self._candidate_location = location
                self._moving_streak = 1
                return {"status": "movement_candidate", "speed_kmh": speed}
            self._moving_streak += 1
            candidate_distance = self.haversine_km(
                self._candidate_location[0],
                self._candidate_location[1],
                latitude,
                longitude,
            )
            if (
                self._moving_streak < START_SAMPLES
                or candidate_distance < START_MIN_DISTANCE_KM
            ):
                return {
                    "status": "movement_candidate",
                    "speed_kmh": speed,
                    "candidate_distance_km": round(candidate_distance, 3),
                }
            plan = self.memory.pending_travel_plan()
            trip_id = self.memory.start_trip(
                latitude,
                longitude,
                destination=str(plan["destination"]) if plan else "",
                plan_id=int(plan["id"]) if plan else None,
            )
            active = self.memory.active_trip()
            self._reset_start_candidate()
            if active is None:
                return {"status": "error"}
            active["id"] = trip_id
            newly_started = True

        metadata = dict(active.get("metadata") or {})
        last_at = self._datetime(metadata.get("last_at"))
        elapsed = 0.0 if last_at is None else max(0.0, (now - last_at).total_seconds())
        elapsed = min(elapsed, 300.0)
        last_lat = self._number(metadata.get("last_lat"))
        last_lon = self._number(metadata.get("last_lon"))
        distance = float(active.get("distance_km") or 0)
        if last_lat is not None and last_lon is not None:
            segment = self.haversine_km(last_lat, last_lon, latitude, longitude)
            implied_speed = segment / (elapsed / 3600) if elapsed > 0 else 0.0
            plausible_limit = max(30.0, speed * 2.5 + 15.0)
            if (
                speed >= STOPPED_KMH
                and segment <= 5.0
                and implied_speed <= plausible_limit
            ):
                distance += segment
        moving_seconds = float(active.get("moving_seconds") or 0)
        if speed >= STOPPED_KMH:
            moving_seconds += elapsed
        max_speed = max(float(active.get("max_speed_kmh") or 0), speed)
        stop_count = int(active.get("stop_count") or 0)
        stationary_since = active.get("stationary_since")

        if speed < STOPPED_KMH:
            if not stationary_since:
                stationary_since = now.isoformat()
                metadata["stop_registered"] = False
            stopped_for = (
                now - (self._datetime(stationary_since) or now)
            ).total_seconds()
            if stopped_for >= 300 and not metadata.get("stop_registered"):
                stop_count += 1
                metadata["stop_registered"] = True
        else:
            stationary_since = None
            metadata["stop_registered"] = False

        metadata.update(
            {
                "last_at": now.isoformat(),
                "last_lat": latitude,
                "last_lon": longitude,
                "current_speed_kmh": speed,
            }
        )
        self.memory.update_trip_progress(
            int(active["id"]),
            distance_km=distance,
            moving_seconds=moving_seconds,
            max_speed_kmh=max_speed,
            stop_count=stop_count,
            stationary_since=stationary_since,
            metadata=metadata,
        )

        last_store = self._datetime(metadata.get("last_store_at"))
        if last_store is None or (now - last_store).total_seconds() >= 60:
            environment = self._environment(states)
            self.memory.add_trip_point(
                int(active["id"]),
                now.isoformat(),
                latitude,
                longitude,
                speed,
                environment.get("temperature"),
                environment.get("humidity"),
                environment.get("pressure"),
                environment,
            )
            metadata["last_store_at"] = now.isoformat()
            self.memory.update_trip_progress(
                int(active["id"]),
                distance_km=distance,
                moving_seconds=moving_seconds,
                max_speed_kmh=max_speed,
                stop_count=stop_count,
                stationary_since=stationary_since,
                metadata=metadata,
            )

        if stationary_since:
            stationary_minutes = (
                now - (self._datetime(stationary_since) or now)
            ).total_seconds() / 60
            if stationary_minutes >= self.arrival_minutes:
                self.memory.finish_trip(int(active["id"]), latitude, longitude)
                return {
                    "status": "arrived",
                    "trip_id": int(active["id"]),
                    "destination": active.get("destination") or "destinazione rilevata",
                }
        return {
            "status": (
                "started"
                if newly_started
                else ("travelling" if speed >= STOPPED_KMH else "stopped")
            ),
            "trip_id": int(active["id"]),
            "speed_kmh": round(speed, 1),
            "distance_km": round(distance, 2),
        }

    def _reset_start_candidate(self) -> None:
        self._moving_streak = 0
        self._candidate_location = None

    def _at_base(self, latitude: float, longitude: float) -> bool:
        profile = self.memory.get_json_setting("vehicle_profile") or {}
        base = profile.get("base") or {}
        base_lat = self._number(base.get("latitude"))
        base_lon = self._number(base.get("longitude"))
        if base_lat is None or base_lon is None:
            return False
        radius_m = self._number(base.get("radius_m")) or DEFAULT_BASE_RADIUS_M
        return self.haversine_km(base_lat, base_lon, latitude, longitude) * 1000 <= radius_m

    def report(self, trip_id: int | None = None) -> dict[str, Any]:
        trip = (
            self.memory.trip_detail(trip_id)
            if trip_id is not None
            else self._latest_trip()
        )
        if trip is None:
            return {"available": False, "message": "Nessun viaggio registrato."}
        moving_seconds = float(trip.get("moving_seconds") or 0)
        distance = float(trip.get("distance_km") or 0)
        average = distance / (moving_seconds / 3600) if moving_seconds > 0 else 0
        started_at = self._datetime(trip.get("started_at"))
        ended_at = self._datetime(trip.get("ended_at")) or datetime.now(timezone.utc)
        elapsed_seconds = (
            max(0.0, (ended_at - started_at).total_seconds())
            if started_at is not None
            else moving_seconds
        )
        return {
            "available": True,
            "id": int(trip["id"]),
            "status": trip["status"],
            "destination": trip.get("destination") or "non indicata",
            "started_at": trip["started_at"],
            "ended_at": trip.get("ended_at"),
            "distance_km": round(distance, 2),
            "duration_minutes": round(elapsed_seconds / 60),
            "moving_minutes": round(moving_seconds / 60),
            "stopped_minutes": round(max(0.0, elapsed_seconds - moving_seconds) / 60),
            "average_speed_kmh": round(average, 1),
            "max_speed_kmh": round(float(trip.get("max_speed_kmh") or 0), 1),
            "stops": int(trip.get("stop_count") or 0),
            "points": len(trip.get("points") or []),
            "current_speed_kmh": round(
                float((trip.get("metadata") or {}).get("current_speed_kmh") or 0),
                1,
            ),
        }

    def dashboard_summary(self) -> dict[str, Any]:
        """Return local trip counters for the compact onboard dashboard."""
        trips = self.memory.list_trips(limit=10000)
        total_distance = sum(float(item.get("distance_km") or 0) for item in trips)
        latest = self.report()
        return {
            "available": bool(trips),
            "total_distance_km": round(total_distance, 1),
            "trip_count": len(trips),
            "latest": latest,
        }

    def export_csv(self, trip_id: int) -> str:
        trip = self.memory.trip_detail(trip_id)
        if trip is None:
            raise KeyError(trip_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "timestamp",
                "latitude",
                "longitude",
                "speed_kmh",
                "temperature_c",
                "humidity_pct",
                "pressure_hpa",
            ]
        )
        for point in trip["points"]:
            writer.writerow(
                [
                    point["observed_at"],
                    point["latitude"],
                    point["longitude"],
                    point["speed_kmh"],
                    point["temperature"],
                    point["humidity"],
                    point["pressure"],
                ]
            )
        return output.getvalue()

    def export_gpx(self, trip_id: int) -> str:
        trip = self.memory.trip_detail(trip_id)
        if trip is None:
            raise KeyError(trip_id)
        name = escape(trip.get("destination") or f"Viaggio {trip_id}")
        points = "".join(
            f'<trkpt lat="{point["latitude"]}" lon="{point["longitude"]}">'
            f'<time>{escape(point["observed_at"])}</time>'
            f'</trkpt>'
            for point in trip["points"]
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<gpx version="1.1" creator="mistermif AI" '
            'xmlns="http://www.topografix.com/GPX/1/1">'
            f"<trk><name>{name}</name><trkseg>{points}</trkseg></trk></gpx>"
        )

    def _latest_trip(self) -> dict[str, Any] | None:
        trips = self.memory.list_trips(limit=1)
        return self.memory.trip_detail(int(trips[0]["id"])) if trips else None

    @classmethod
    def _location(cls, states: list[dict[str, Any]]) -> tuple[float, float] | None:
        for item in states:
            if str(item.get("entity_id", "")).startswith("device_tracker.caravan"):
                attributes = item.get("attributes") or {}
                lat = cls._number(attributes.get("latitude"))
                lon = cls._number(attributes.get("longitude"))
                if lat is not None and lon is not None and (lat != 0 or lon != 0):
                    return lat, lon
        lat = cls._metric(states, ("gps", "lat"), ("latitude",))
        lon = cls._metric(states, ("gps", "lon"), ("longitude",))
        return (lat, lon) if lat is not None and lon is not None else None

    @classmethod
    def _environment(cls, states: list[dict[str, Any]]) -> dict[str, float]:
        result = {}
        mappings = {
            "temperature": (("esterno", "temper"), ("temperature",)),
            "humidity": (("esterno", "umid"), ("humidity",)),
            "pressure": (("baro", "pression"), ("pressure",)),
        }
        for key, groups in mappings.items():
            value = cls._metric(states, *groups)
            if value is not None:
                result[key] = value
        return result

    @classmethod
    def _metric(
        cls,
        states: list[dict[str, Any]],
        *term_groups: tuple[str, ...],
    ) -> float | None:
        for item in states:
            candidate = f'{item.get("entity_id", "")} {item.get("name", "")}'.casefold()
            if any(all(term in candidate for term in group) for group in term_groups):
                value = cls._number(item.get("state"))
                if value is not None:
                    return value
        return None

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0088
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        value = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
