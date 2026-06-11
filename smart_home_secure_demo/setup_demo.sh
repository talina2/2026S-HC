#!/usr/bin/env bash
# Einmalige Einrichtung: CA, Zertifikate und Onboarding aller Demo-Gerät
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"  # shared/ immer auffindbar

echo "1. CERTIFICATE AUTHORITY"
[ -f ca/ca_private_key.pem ] || python3 ca/create_ca.py

# device_id  device_type  onboarding-skript
DEVICES=(
  "temp_sensor_01 temperature_sensor devices/sensor.py"
  "motion_sensor_01 motion_sensor devices/sensor.py"
  "motion_sensor_outdoor_01 motion_sensor devices/sensor.py"
  "motion_sensor_perimeter_01 motion_sensor devices/sensor.py"
  "light_actuator_01 light_actuator devices/actuator.py"
  "heating_actuator_01 heating_actuator devices/actuator.py"
  "shutter_actuator_01 shutter_actuator devices/actuator.py"
  "alarm_actuator_01 alarm_actuator devices/actuator.py"
  "weather_station_01 weather_station hub/gateway.py"
  "ventilation_actuator_01 ventilation_actuator devices/actuator.py"
)

echo "2. Zertifikate ausstellen falls nicht vorhanden"
for entry in "${DEVICES[@]}"; do
  set -- $entry
  if [ -f "devices/device_credentials/$1/device_certificate.json" ]; then
    echo "  $1: Zertifikat existiert bereits"
  else
    python3 ca/issue_device_certificate.py "$1" "$2"
  fi
done

echo "Onboarding-Anfragen erstellen"
for entry in "${DEVICES[@]}"; do
  set -- $entry
  python3 "$3" onboard "$1"
done

echo "4. Hub/Commissioner"
python3 hub/commissioner.py

echo "5. Session Keys abschließen (finalize)"
for entry in "${DEVICES[@]}"; do
  set -- $entry
  python3 "$3" finalize "$1"
done

echo
echo "Setup fertig -> './run_demo.sh' starten"