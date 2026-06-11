#!/usr/bin/env bash
# Startet das komplette Smart Home: Broker + alle Komponenten
set -uo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"  # shared/ immer auffindbar
mkdir -p logs/run

PIDS=()
cleanup() {
  echo
  echo "Stoppe alle Komponenten..."
  for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done
}
trap cleanup INT TERM EXIT

start() {  # start <name> <befehl...>
  local name="$1"; shift
  echo "  starte $name"
  "$@" >"logs/run/$name.log" 2>&1 &
  PIDS+=($!)
}

echo "BROKER MOSQUITTO"
mosquitto -c broker/mosquitto.conf >logs/run/broker.log 2>&1 &
PIDS+=($!)
sleep 2

echo "Hub-Komponenten"
start hub_receiver        python3 hub/telemetry_receiver.py
start automation_service  python3 hub/automation_service.py
start broker_observer     python3 broker/broker_observer.py
start dashboard           python3 dashboard/server.py
start heartbeat_monitor   python3 hub/heartbeat_monitor.py

echo "AKTOREN"
start light_actuator      python3 devices/actuator.py listen light_actuator_01
start heating_actuator    python3 devices/actuator.py listen heating_actuator_01
start shutter_actuator    python3 devices/actuator.py listen shutter_actuator_01
start alarm_actuator      python3 devices/actuator.py listen alarm_actuator_01
start ventilation_actuator python3 devices/actuator.py listen ventilation_actuator_01
sleep 1

echo "SENSOREN"
start temp_sensor         python3 devices/sensor.py send temp_sensor_01
start motion_sensor       python3 devices/sensor.py send motion_sensor_01
start motion_perimeter    python3 devices/sensor.py send motion_sensor_perimeter_01 perimeter

echo "Heterogenes Gerät (HTTP) + Gateway"
start http_weather        python3 devices/http_weather_station.py
sleep 1
start gateway             python3 hub/gateway.py run weather_station_01

echo "Heartbeats pro Gerät"
start hb_temp_sensor_01     python3 devices/heartbeat_sender.py temp_sensor_01
start hb_motion_sensor_01   python3 devices/heartbeat_sender.py motion_sensor_01
start hb_motion_outdoor_01  python3 devices/heartbeat_sender.py motion_sensor_outdoor_01
start hb_motion_perimeter_01 python3 devices/heartbeat_sender.py motion_sensor_perimeter_01
start hb_light_actuator_01  python3 devices/heartbeat_sender.py light_actuator_01
start hb_heating_actuator_01 python3 devices/heartbeat_sender.py heating_actuator_01
start hb_shutter_actuator_01 python3 devices/heartbeat_sender.py shutter_actuator_01
start hb_alarm_actuator_01   python3 devices/heartbeat_sender.py alarm_actuator_01
start hb_weather_station_01  python3 devices/heartbeat_sender.py weather_station_01
start hb_ventilation_actuator_01 python3 devices/heartbeat_sender.py ventilation_actuator_01
echo
echo "Dashboard: http://localhost:8080"
wait