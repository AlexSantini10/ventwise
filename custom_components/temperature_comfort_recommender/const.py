"""Constants for Temperature Comfort Recommender."""

DOMAIN = "temperature_comfort_recommender"
NAME = "Temperature Comfort Recommender"
MANUFACTURER = "VentWise"

DEFAULT_TARGET_TEMPERATURE_C = 22.0
DEFAULT_SOFT_OUTDOOR_THRESHOLD_C = 22.0
DEFAULT_MINIMUM_SCORE = 0.35
DEFAULT_COOLDOWN_MINUTES = 60
DEFAULT_STABILITY_MINUTES = 10
DEFAULT_QUIET_HOURS_START = "22:00:00"
DEFAULT_QUIET_HOURS_END = "07:00:00"
DEFAULT_ROOM_WEIGHT = 1.0
DEFAULT_ROOM_COUNT = 1

CONF_TARGET_TEMPERATURE_C = "target_temperature_c"
CONF_SOFT_OUTDOOR_THRESHOLD_C = "soft_outdoor_threshold_c"
CONF_MINIMUM_SCORE = "minimum_score"
CONF_COOLDOWN_MINUTES = "cooldown_minutes"
CONF_STABILITY_MINUTES = "stability_minutes"
CONF_QUIET_HOURS_ENABLED = "quiet_hours_enabled"
CONF_QUIET_HOURS_START = "quiet_hours_start"
CONF_QUIET_HOURS_END = "quiet_hours_end"
CONF_OUTDOOR_TEMPERATURE_ENTITY_ID = "outdoor_temperature_entity_id"
CONF_OUTDOOR_HUMIDITY_ENTITY_ID = "outdoor_humidity_entity_id"
CONF_WIND_SPEED_ENTITY_ID = "wind_speed_entity_id"
CONF_ROOMS = "rooms"
CONF_ROOM_NAME = "name"
CONF_ROOM_TEMPERATURE_ENTITY_ID = "temperature_entity_id"
CONF_ROOM_HUMIDITY_ENTITY_ID = "humidity_entity_id"
CONF_ROOM_WEIGHT = "weight"
CONF_ROOM_COUNT = "room_count"

MIN_ROOM_WEIGHT = 0.1
MAX_ROOM_WEIGHT = 3.0
MAX_ROOM_COUNT = 8
