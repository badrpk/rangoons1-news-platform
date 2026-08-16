from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable, Optional


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalise_timestamp(value: str) -> str:
    return _parse_time(value).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Event:
    id: str
    timestamp: str
    title: str
    source: str
    body: str = ""
    tags: tuple[str, ...] = ()


class ChronaArchive:
    """Deterministic local timeline/archive store for timestamped events."""

    def __init__(self) -> None:
        self._events: dict[str, Event] = {}

    @staticmethod
    def event_id(*, timestamp: str, title: str, source: str) -> str:
        payload = "\n".join(
            [
                _normalise_timestamp(timestamp),
                title.strip(),
                source.strip(),
            ]
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:24]

    def add(
        self,
        *,
        timestamp: str,
        title: str,
        source: str,
        body: str = "",
        tags: Iterable[str] = (),
    ) -> Event:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source is required")

        normalised = _normalise_timestamp(timestamp)
        event_id = self.event_id(
            timestamp=normalised,
            title=title,
            source=source,
        )
        event = Event(
            id=event_id,
            timestamp=normalised,
            title=title.strip(),
            source=source.strip(),
            body=body.strip(),
            tags=tuple(sorted({str(tag).strip().lower() for tag in tags if str(tag).strip()})),
        )
        self._events[event.id] = event
        return event

    def get(self, event_id: str) -> Optional[Event]:
        return self._events.get(event_id)

    def timeline(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        tag: str | None = None,
        source: str | None = None,
        newest_first: bool = False,
    ) -> list[Event]:
        start_dt = _parse_time(start) if start else None
        end_dt = _parse_time(end) if end else None
        wanted_tag = tag.strip().lower() if tag else None
        wanted_source = source.strip().lower() if source else None

        result: list[Event] = []
        for event in self._events.values():
            dt = _parse_time(event.timestamp)
            if start_dt and dt < start_dt:
                continue
            if end_dt and dt > end_dt:
                continue
            if wanted_tag and wanted_tag not in event.tags:
                continue
            if wanted_source and event.source.lower() != wanted_source:
                continue
            result.append(event)

        result.sort(
            key=lambda event: (_parse_time(event.timestamp), event.id),
            reverse=newest_first,
        )
        return result

    def search(self, query: str) -> list[Event]:
        needle = query.strip().lower()
        if not needle:
            return []
        result = [
            event
            for event in self._events.values()
            if needle in event.title.lower()
            or needle in event.body.lower()
            or needle in event.source.lower()
            or any(needle in tag for tag in event.tags)
        ]
        result.sort(key=lambda event: (_parse_time(event.timestamp), event.id))
        return result

    def snapshot(self) -> dict:
        events = [asdict(event) for event in self.timeline()]
        for event in events:
            event["tags"] = list(event["tags"])
        canonical = json.dumps(events, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return {
            "count": len(events),
            "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "events": events,
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.snapshot(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "ChronaArchive":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        archive = cls()
        for item in data.get("events", []):
            archive.add(
                timestamp=item["timestamp"],
                title=item["title"],
                source=item["source"],
                body=item.get("body", ""),
                tags=item.get("tags", []),
            )
        return archive


__all__ = ["ChronaArchive", "Event"]
