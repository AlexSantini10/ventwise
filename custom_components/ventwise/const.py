"""Constants for VentWise."""

DOMAIN = "ventwise"
NAME = "VentWise"
MANUFACTURER = "VentWise"
UNIT_CELSIUS = "°C"
UNIT_FAHRENHEIT = "°F"
UNIT_METERS_PER_SECOND = "m/s"
UNIT_KILOMETERS_PER_HOUR = "km/h"
UNIT_MILES_PER_HOUR = "mph"
UNIT_KNOTS = "kn"
DEFAULT_TEMPERATURE_UNIT = UNIT_CELSIUS
DEFAULT_WIND_SPEED_UNIT = UNIT_METERS_PER_SECOND

DEFAULT_TARGET_TEMPERATURE_C = 22.0
DEFAULT_AUTO_COMFORT_TEMPERATURE = False
DEFAULT_MINIMUM_SCORE = 0.35
DEFAULT_COOLDOWN_MINUTES = 60
DEFAULT_STABILITY_MINUTES = 10
DEFAULT_ROOM_ACTION_CHANGE_HOLD_MINUTES = 5
DEFAULT_ROOM_ACTION_LOCKOUT_MINUTES = 30
DEFAULT_QUIET_HOURS_START = "22:00:00"
DEFAULT_QUIET_HOURS_END = "07:00:00"
DEFAULT_ROOM_COUNT = 1
DEFAULT_CO2_THRESHOLD_PPM = 1000.0
DEFAULT_TARGET_HUMIDITY_PERCENT = 50.0
DEFAULT_URGENT_CLOSE_DURING_QUIET_HOURS = False
DIAGNOSTIC_NOTIFICATION_LEVEL_ESSENTIAL = "essential"
DIAGNOSTIC_NOTIFICATION_LEVEL_DIAGNOSTIC = "diagnostic"
DEFAULT_DIAGNOSTIC_NOTIFICATION_LEVEL = DIAGNOSTIC_NOTIFICATION_LEVEL_ESSENTIAL
DEFAULT_DEBUG_MODE_ENABLED = False
OUTDOOR_SOURCE_FORECAST = "forecast"
OUTDOOR_SOURCE_OVERRIDE = "override"

CONF_TARGET_TEMPERATURE_C = "target_temperature_c"
CONF_TEMPERATURE_UNIT = "temperature_unit"
CONF_WIND_SPEED_UNIT = "wind_speed_unit"
CONF_AUTO_COMFORT_TEMPERATURE = "auto_comfort_temperature"
CONF_TARGET_HUMIDITY_PERCENT = "target_humidity_percent"
CONF_MINIMUM_SCORE = "minimum_score"
CONF_COOLDOWN_MINUTES = "cooldown_minutes"
CONF_STABILITY_MINUTES = "stability_minutes"
CONF_QUIET_HOURS_ENABLED = "quiet_hours_enabled"
CONF_QUIET_HOURS_START = "quiet_hours_start"
CONF_QUIET_HOURS_END = "quiet_hours_end"
CONF_URGENT_CLOSE_DURING_QUIET_HOURS = "urgent_close_during_quiet_hours"
CONF_OUTDOOR_WEATHER_ENTITY_ID = "outdoor_weather_entity_id"
CONF_OUTDOOR_TEMPERATURE_OVERRIDE = "outdoor_temperature_override"
CONF_OUTDOOR_TEMPERATURE_SOURCE = "outdoor_temperature_source"
CONF_OUTDOOR_HUMIDITY_SOURCE = "outdoor_humidity_source"
CONF_OUTDOOR_HUMIDITY_OVERRIDE = "outdoor_humidity_override"
CONF_WIND_SPEED_SOURCE = "wind_speed_source"
CONF_WIND_SPEED_OVERRIDE = "wind_speed_override"
CONF_OUTDOOR_TEMPERATURE_ENTITY_ID = "outdoor_temperature_entity_id"
CONF_OUTDOOR_HUMIDITY_ENTITY_ID = "outdoor_humidity_entity_id"
CONF_WIND_SPEED_ENTITY_ID = "wind_speed_entity_id"
# Optional exposure inputs remain advisory unless the corresponding user
# policy is explicitly set.
CONF_POLLUTION_POLICY = "pollution_policy"
CONF_POLLEN_POLICY = "pollen_policy"
CONF_OPEN_METEO_AIR_QUALITY_ENABLED = "open_meteo_air_quality_enabled"
CONF_AIR_QUALITY_ENTITY_IDS = "air_quality_entity_ids"
CONF_EXPOSURE_POLICIES = "exposure_policies"

# The keys match Open-Meteo's documented current-condition variables.
AIR_QUALITY_VARIABLES = (
    "pm2_5", "pm10", "nitrogen_dioxide", "ozone", "carbon_monoxide",
    "sulphur_dioxide", "european_aqi", "alder_pollen", "birch_pollen",
    "grass_pollen", "mugwort_pollen", "olive_pollen", "ragweed_pollen",
)
CONF_NOTIFICATION_DEVICE_ID = "notification_device_id"
CONF_NOTIFICATION_ENABLED = "notification_enabled"
CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED = "home_assistant_notification_enabled"
CONF_DIAGNOSTIC_NOTIFICATION_LEVEL = "diagnostic_notification_level"
CONF_DEBUG_MODE_ENABLED = "debug_mode_enabled"
CONF_CO2_ENABLED = "co2_enabled"
CONF_CO2_ENTITY_ID = "co2_entity_id"
CONF_CO2_THRESHOLD_PPM = "co2_threshold_ppm"
CONF_ENABLED = "enabled"
CONF_ROOMS = "rooms"
CONF_ROOM_KIND = "kind"
CONF_ROOM_ID = "room_id"
CONF_ROOM_NAME = "name"
CONF_ROOM_ENABLED = "enabled"
CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED = "target_temperature_c_override_enabled"
CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C = "target_temperature_c_override"
CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED = "target_humidity_percent_override_enabled"
CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE = "target_humidity_percent_override"
CONF_ROOM_TEMPERATURE_ENTITY_ID = "temperature_entity_id"
CONF_ROOM_HUMIDITY_ENTITY_ID = "humidity_entity_id"
CONF_ROOM_CO2_ENTITY_ID = "co2_entity_id"
CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS = "window_sensor_entity_ids"
CONF_ROOM_START_ENTITY_ID = "start_entity_id"
CONF_ROOM_STOP_ENTITY_ID = "stop_entity_id"
CONF_ROOM_ACTION_CHANGE_HOLD_MINUTES = "action_change_hold_minutes"
CONF_ROOM_ACTION_LOCKOUT_MINUTES = "action_lockout_minutes"
# Optional room calibration values; all use canonical SI units.
CONF_ROOM_VOLUME_M3 = "volume_m3"
CONF_ROOM_OPENING_AREA_M2 = "opening_area_m2"
CONF_ROOM_OPENING_FRACTION = "opening_fraction"
CONF_ROOM_EXPOSURE = "exposure"
CONF_ROOM_THERMAL_RESISTANCE = "thermal_resistance_m2k_w"
CONF_ROOM_THERMAL_MASS = "thermal_mass_kj_k"
CONF_ROOM_SURFACE_TEMPERATURE_ENTITY_ID = "surface_temperature_entity_id"
CONF_ROOM_SELECTION = "room_selection"
CONF_ROOM_COUNT = "room_count"
CONF_RUNTIME_STATE = "_runtime_state"
CONF_RUNTIME_LAST_ACTION_SIGNATURE = "last_action_signature"
CONF_RUNTIME_LAST_ACTION_STARTED_AT = "last_action_started_at"
CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE = "last_notification_signature"
CONF_RUNTIME_LAST_NOTIFICATION_AT = "last_notification_at"
CONF_RUNTIME_NOTIFICATION_MARKERS = "notification_markers"
CONF_RUNTIME_ROOM_ACTION_GUARDS = "room_action_guards"
CONF_RUNTIME_DIAGNOSTIC_ISSUE = "diagnostic_issue"
MAX_ROOM_COUNT = 8
