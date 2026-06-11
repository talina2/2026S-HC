MQTT_HOST = "localhost"
MQTT_PORT = 1883

# Sensoren -> Hub
TOPIC_TEMPERATURE = "home/livingroom/temperature/telemetry"
TOPIC_MOTION = "home/livingroom/motion/telemetry"

TOPIC_TELEMETRY_WILDCARD = "home/+/+/telemetry"

# Automation Service -> Aktoren
TOPIC_LIGHT_COMMAND = "home/livingroom/light/command"
TOPIC_HEATING_COMMAND = "home/livingroom/heating/command"
TOPIC_SHUTTER_COMMAND = "home/livingroom/shutter/command"
TOPIC_ALARM_COMMAND = "home/livingroom/alarm/command"
TOPIC_VENTILATION_COMMAND = "home/livingroom/ventilation/command"

# Welcher Gerätetyp lauscht auf welchem Befehls-Topic
COMMAND_TOPIC_BY_TYPE = {
    "light_actuator": TOPIC_LIGHT_COMMAND,
    "heating_actuator": TOPIC_HEATING_COMMAND,
    "shutter_actuator": TOPIC_SHUTTER_COMMAND,
    "alarm_actuator": TOPIC_ALARM_COMMAND,
    "ventilation_actuator": TOPIC_VENTILATION_COMMAND,
}

# Heartbeat Geräte -> Hub: regelmäßiges Lebenszeichen
TOPIC_HEARTBEAT = "home/heartbeat"

# Wildcard, mit dem der Broker-Observer ALLES im Haus mithören kann
TOPIC_ALL = "home/#"

ALLOWED_DEVICE_TYPES = {
    "temperature_sensor",
    "motion_sensor",
    "light_actuator",
    "heating_actuator",
    "shutter_actuator",
    "alarm_actuator",
    "weather_station",
    "ventilation_actuator",
}