from __future__ import annotations

import datetime
import logging
import re
from dataclasses import dataclass
from functools import cached_property, partial
from typing import Any, Dict, Iterable, List, NamedTuple, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.util import dt
from weiche import Schiene

from custom_components.db_train_tracker.const import (
    DEFAULT_DURATION,
    DEFAULT_FILTERED_REGULAR_EXPRESSIONS,
    DEFAULT_MAPPINGS,
    DEFAULT_MAX_RESULTS,
    DEFAULT_REMOVE_TIME_DUPLICATES,
)

_LOGGER = logging.getLogger(__name__)


class GathererConfig(NamedTuple):
    origin: str
    calendars: Tuple[str, ...]
    scan_duration_hours: int = DEFAULT_DURATION
    filtered_regular_expressions: Tuple[str, ...] = DEFAULT_FILTERED_REGULAR_EXPRESSIONS
    mappings: Tuple[Tuple[str, str], ...] = DEFAULT_MAPPINGS
    max_results: int = DEFAULT_MAX_RESULTS
    remove_same_time_duplicates: bool = DEFAULT_REMOVE_TIME_DUPLICATES

    def get_compiled_expressions(self) -> Tuple[re.Pattern, ...]:
        return tuple(re.compile(expr, re.IGNORECASE | re.UNICODE) for expr in self.filtered_regular_expressions)

    @property
    def scan_duration_dict(self) -> Dict[str, Any]:
        hours = self.scan_duration_hours
        return {"hours": hours, "minutes": 0, "seconds": 0}


@dataclass
class CalendarEntryResult:
    calendar: str
    start: str
    end: str
    summary: str
    description: str | None = None
    location: str | None = None

    @cached_property
    def start_dt(self) -> datetime.datetime | datetime.date:
        return dt.parse_datetime(self.start) or dt.parse_date(self.start)

    @cached_property
    def end_dt(self) -> datetime.datetime | datetime.date:
        return dt.parse_datetime(self.end) or dt.parse_date(self.end)


class PlannedTravelTime(NamedTuple):
    start: datetime.datetime
    end: datetime.datetime
    origin: str
    destination: str


class PossibleTravelTimes(NamedTuple):
    planned_travel_time: PlannedTravelTime
    connections: Tuple[TravelInformation, ...]

    @property
    def origin(self) -> str:
        return self.planned_travel_time.origin

    @property
    def destination(self) -> str:
        return self.planned_travel_time.destination

    @property
    def start(self) -> datetime.datetime:
        if len(self.connections) == 0:
            return self.planned_travel_time.start
        else:
            return self.connections[0].departure_dt

    @property
    def next_start(self) -> datetime.datetime | None:
        if len(self.connections) < 2:
            return None
        else:
            return self.connections[1].departure_dt

    @property
    def start_string(self) -> str:
        if len(self.connections) == 0:
            return "00:00"
        return self.connections[0].departure

    @property
    def next_start_string(self) -> str:
        if len(self.connections) < 2:
            return "00:00"
        return self.connections[1].departure

    @property
    def end(self) -> datetime.datetime:
        if len(self.connections) == 0:
            return self.planned_travel_time.end
        return self.connections[0].arrival_dt

    @property
    def next_end(self) -> datetime.datetime | None:
        if len(self.connections) < 2:
            return None
        return self.connections[1].arrival_dt

    @property
    def end_string(self) -> str:
        if len(self.connections) == 0:
            return "00:00"
        return self.connections[0].arrival

    @property
    def next_end_string(self) -> str:
        if len(self.connections) < 2:
            return "00:00"
        return self.connections[1].arrival

    @property
    def departure_delay(self) -> int:
        if len(self.connections) == 0:
            return 0
        return self.connections[0].departure_delay

    @property
    def next_departure_delay(self) -> int:
        if len(self.connections) < 2:
            return 0
        return self.connections[1].departure_delay

    @property
    def arrival_delay(self) -> int:
        if len(self.connections) == 0:
            return 0
        return self.connections[0].arrival_delay

    @property
    def next_arrival_delay(self) -> int:
        if len(self.connections) < 2:
            return 0
        return self.connections[1].arrival_delay

    @property
    def ontime(self) -> bool:
        if len(self.connections) == 0:
            return True
        return self.connections[0].ontime

    @property
    def next_ontime(self) -> bool:
        if len(self.connections) < 2:
            return True
        return self.connections[1].ontime

    @property
    def canceled(self) -> bool:
        if len(self.connections) == 0:
            return False
        return self.connections[0].canceled

    @property
    def next_canceled(self) -> bool:
        if len(self.connections) < 2:
            return False
        return self.connections[1].canceled

    @property
    def transfers(self) -> int:
        if len(self.connections) == 0:
            return 0
        return self.connections[0].transfers

    @property
    def next_transfers(self) -> int:
        if len(self.connections) < 2:
            return 0
        return self.connections[1].transfers

    @property
    def time(self) -> str:
        if len(self.connections) == 0:
            return "00:00"
        return self.connections[0].time

    @property
    def next_time(self) -> str:
        if len(self.connections) < 2:
            return "00:00"
        return self.connections[1].time

    @property
    def products(self) -> tuple[str, ...]:
        if len(self.connections) == 0:
            return tuple()
        else:
            return self.connections[0].products

    @property
    def next_products(self) -> tuple[str, ...]:
        if len(self.connections) < 2:
            return tuple()
        else:
            return self.connections[1].products

    def to_dict(self) -> dict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "start": self.start,
            "end": self.end,
            "start_string": self.start_string,
            "end_string": self.end_string,
            "time": self.time,
            "ontime": self.ontime,
            "canceled": self.canceled,
            "products": self.products,
            "departure_delay": self.departure_delay,
            "connections": [conn.to_dict() for conn in self.connections],
        }


class TravelInformation(NamedTuple):
    reference_time: datetime.datetime
    departure: str
    arrival: str
    ontime: bool
    transfers: int
    time: str
    products: tuple[str, ...]
    price: str | None
    departure_delay: int
    arrival_delay: int
    canceled: bool
    details_url: str

    def _normalize_time_string(self, time: str) -> datetime.datetime:
        local_reference = dt.as_local(self.reference_time).replace(second=0, microsecond=0)
        normalized_dt = datetime.datetime.strptime(time, "%H:%M")
        new_reference = local_reference.replace(hour=normalized_dt.hour, minute=normalized_dt.minute)
        time_check = new_reference
        if dt.now() > local_reference:
            # Get one hour in advance as deutsche bahn seems to send data before the current time if
            # requesting data from earlier than now
            time_check = time_check + datetime.timedelta(hours=1)
        if time_check.time() < local_reference.time() and new_reference.time():
            new_reference += datetime.timedelta(days=1)
        return new_reference

    @property
    def departure_dt(self) -> datetime.datetime:
        return self._normalize_time_string(self.departure)

    @property
    def arrival_dt(self) -> datetime.datetime:
        return self._normalize_time_string(self.arrival)

    @property
    def time_timedelta(self) -> datetime.timedelta:
        split_time = self.time.split(":")
        hours = int(split_time[0])
        minutes = 0
        if len(split_time) > 1:
            minutes = int(split_time[1])

        return datetime.timedelta(hours=hours, minutes=minutes)

    @classmethod
    def from_dict(self, reference_time: datetime.datetime, data: Dict[str, Any]) -> TravelInformation:
        return TravelInformation(
            reference_time=reference_time,
            departure=data.get("departure", "00:00"),
            arrival=data.get("arrival", "00:00"),
            ontime=data.get("ontime", True),
            transfers=data.get("transfers", None),
            time=data.get("time", "00:00"),
            price=data.get("price", None),
            products=tuple(data["products"]),
            arrival_delay=data.get("delay", {}).get("delay_arrival", 0),
            departure_delay=data.get("delay", {}).get("delay_departure", 0),
            canceled=data.get("canceled", False),
            details_url=data.get("details", None),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "departure": self.departure_dt,
            "arrival": self.arrival_dt,
            "departure_string": self.departure,
            "arrival_string": self.arrival,
            "ontime": self.ontime,
            "transfers": self.transfers,
            "time": self.time,
            "products": self.products,
            "arrival_delay": self.arrival_delay,
            "delay": self.departure_delay,
            "canceled": self.canceled,
        }


class GathererResult(NamedTuple):
    travel_times: Tuple[PossibleTravelTimes, ...]

    @property
    def exists(self) -> bool:
        return len(self.travel_times) > 0

    @property
    def origin(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].origin

    @property
    def destination(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].destination

    @property
    def start(self) -> datetime.datetime | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].start

    @property
    def start_string(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].start_string

    @property
    def end(self) -> datetime.datetime | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].end

    @property
    def end_string(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].end_string

    @property
    def time(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].time

    @property
    def departure_delay(self) -> int:
        if len(self.travel_times) == 0:
            return 0
        return self.travel_times[0].departure_delay

    @property
    def arrival_delay(self) -> int:
        if len(self.travel_times) == 0:
            return 0
        return self.travel_times[0].arrival_delay

    @property
    def products(self) -> tuple[str, ...]:
        if len(self.travel_times) == 0:
            return tuple()
        return self.travel_times[0].products

    @property
    def ontime(self) -> bool:
        if len(self.travel_times) == 0:
            return True
        return self.travel_times[0].ontime

    @property
    def canceled(self) -> bool:
        if len(self.travel_times) == 0:
            return False
        return self.travel_times[0].canceled

    @property
    def connection(self) -> PossibleTravelTimes | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0]

    @property
    def next_start(self) -> datetime.datetime | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].next_start

    @property
    def next_start_string(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].next_start_string

    @property
    def next_end(self) -> datetime.datetime | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].next_end

    @property
    def next_end_string(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].next_end_string

    @property
    def next_time(self) -> str | None:
        if len(self.travel_times) == 0:
            return None
        return self.travel_times[0].next_time

    @property
    def next_departure_delay(self) -> int:
        if len(self.travel_times) == 0:
            return 0
        return self.travel_times[0].next_departure_delay

    @property
    def next_arrival_delay(self) -> int:
        if len(self.travel_times) == 0:
            return 0
        return self.travel_times[0].next_arrival_delay

    @property
    def next_products(self) -> tuple[str, ...]:
        if len(self.travel_times) == 0:
            return tuple()
        return self.travel_times[0].next_products

    @property
    def next_ontime(self) -> bool:
        if len(self.travel_times) == 0:
            return True
        return self.travel_times[0].next_ontime

    @property
    def next_canceled(self) -> bool:
        if len(self.travel_times) == 0:
            return False
        return self.travel_times[0].next_canceled

    @property
    def next_connection(self) -> PossibleTravelTimes | None:
        if len(self.travel_times) < 2:
            return None
        return self.travel_times[1]


def _convert_destination(destination: str, mappings: Iterable[Tuple[str, str]]) -> str:
    destination = destination.strip()
    for pattern, replacement in mappings:
        if re.match(pattern, destination):
            return replacement
    return destination


def _force_convert_to_datetime(item: datetime.datetime | datetime.date) -> datetime.datetime:
    if isinstance(item, datetime.datetime):
        return dt.as_local(item)
    return dt.as_local(datetime.datetime(year=item.year, month=item.month, day=item.day))


class DataGatherer:
    def __init__(self, hass: HomeAssistant, schiene: Schiene) -> None:
        self.schiene = schiene
        self.hass = hass

    async def _get_calendar_entries(self, config: GathererConfig) -> List[CalendarEntryResult]:
        calendar_entries: List[CalendarEntryResult] = []
        for calendar in config.calendars:
            _LOGGER.debug(f"Checking calendar {calendar}")
            state = self.hass.states.get(calendar)
            # Skip any calendars which do not work
            if state is None or state.state == "unavailable":
                continue

            payload = await self.hass.services.async_call(
                "calendar",
                "get_events",
                service_data={
                    "entity_id": calendar,
                    "start_date_time": dt.now().isoformat(),
                    "duration": config.scan_duration_dict,
                },
                return_response=True,
                blocking=True,
            )
            calendar_entries.extend(
                CalendarEntryResult(calendar=calendar, **event_dict) for event_dict in payload[calendar]["events"]
            )
        _LOGGER.debug(f"Found {len(calendar_entries)} calendar entries")
        return sorted(calendar_entries, key=lambda e: _force_convert_to_datetime(e.start_dt))

    async def get_planned_travel_times(self, config: GathererConfig) -> List[PlannedTravelTime]:
        planned_travel_times = []
        for entry in await self._get_calendar_entries(config):
            for expr in config.get_compiled_expressions():
                if match := expr.match(entry.summary):
                    groupdict = match.groupdict()
                    origin = groupdict.get("origin") or config.origin
                    destination = groupdict.get("destination") or match.groups()[-1]
                    _LOGGER.debug(f"Found calendar candidate {entry}")

                    if isinstance(entry.start_dt, datetime.datetime) and isinstance(entry.end_dt, datetime.datetime):
                        planned_travel_times.append(
                            PlannedTravelTime(
                                start=entry.start_dt,
                                end=entry.end_dt,
                                origin=_convert_destination(origin, config.mappings),
                                destination=_convert_destination(destination, config.mappings),
                            )
                        )
                        break
        return planned_travel_times

    def _deduplicate_connections(self, connections: List[TravelInformation]) -> List[TravelInformation]:
        # Remove all connections which have the same departure and arrival time
        # This is necessary as the db api sometimes returns the same connection twice
        # if the connection has multiple stops
        unique_connections = []
        entries_group: Dict[Tuple[datetime.datetime, datetime.datetime], List[TravelInformation]] = {}
        for conn in connections:
            match_tuple = (conn.departure_dt, conn.arrival_dt)
            entries_group.setdefault(match_tuple, []).append(conn)

        for entry in entries_group:
            candidates = [candidate for candidate in entries_group[entry] if not candidate.canceled]
            if len(candidates) == 0:
                unique_connections.append(entries_group[entry][0])
            else:
                unique_connections.append(candidates[0])

        return sorted(unique_connections, key=lambda c: c.departure_dt)

    async def get_travel_times_of(
        self, planned_travel_time: PlannedTravelTime, config: GathererConfig
    ) -> PossibleTravelTimes:
        connections = await self.hass.async_add_executor_job(
            partial(
                self.schiene.connections,
                origin=planned_travel_time.origin,
                destination=planned_travel_time.destination,
                dt=dt.as_local(planned_travel_time.start),
            )
        )

        all_travel_connections = [TravelInformation.from_dict(planned_travel_time.start, conn) for conn in connections]

        # Remove all travel connections which are before the planned travel time
        travel_connections = [conn for conn in all_travel_connections if conn.departure_dt >= planned_travel_time.start]
        if config.remove_same_time_duplicates:
            travel_connections = self._deduplicate_connections(travel_connections)

        max_results = config.max_results
        travel_connections = travel_connections[:max_results]

        return PossibleTravelTimes(
            planned_travel_time=planned_travel_time,
            connections=tuple(travel_connections),
        )

    async def collect(self, config: GathererConfig) -> GathererResult:
        travel_times = await self.get_planned_travel_times(config)
        possible_travel_times = [await self.get_travel_times_of(planned_time, config) for planned_time in travel_times]

        return GathererResult(travel_times=tuple(possible_travel_times))
