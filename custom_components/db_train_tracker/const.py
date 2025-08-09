from typing import Tuple

DOMAIN = "db_train_tracker"
CONF_CALENDARS = "calendars"
CONF_HOME_STATION = "home_station"
CONF_DURATION = "scan_duration_hours"
CONF_FILTERED_REGULAR_EXPRESSIONS = "regular_expression_filters"
CONF_MAPPINGS = "station_mappings"
CONF_MAX_RESULTS = "max_train_results"
CONF_REMOVE_TIME_DUPLICATES = "remove_time_duplicates"
CONF_PROXY = "proxy"

DEFAULT_DURATION = 48
DEFAULT_MAX_RESULTS = 5
DEFAULT_FILTERED_REGULAR_EXPRESSIONS = (
    "Blocker[:]?[ ]*Travel[ ]*to(.+)",
    "Train[ ]*Travel[ ]*to(.+)",
    "Train[ ]*Travel[ ]*from(?P<origin>.+) to(?P<destination>.+)",
    "(?P<origin>.+)→(?P<destination>.+)",
    "(?P<origin>.+)➞(?P<destination>.+)",
)
DEFAULT_FILTERED_REGULAR_EXPRESSIONS_STRING = ";".join(DEFAULT_FILTERED_REGULAR_EXPRESSIONS)
DEFAULT_MAPPINGS: Tuple[Tuple[str, str], ...] = tuple()
DEFAULT_MAPPINGS_STRING = ";".join(",".join(mapping) for mapping in DEFAULT_MAPPINGS)
DEFAULT_REMOVE_TIME_DUPLICATES: bool = True
DEFAULT_PROXY: str = ""
