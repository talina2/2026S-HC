# Sicherer Smart-Home Demonstrator

Prototyp einer verteilten Smart-Home-Infrastruktur mit sicherem Geräte-Onboarding
(angelehnt an Matter-Commissioning) und Ende-zu-Ende-verschlüsselter Kommunikation
über einen nicht vertrauenswürdigen MQTT-Broker. Sensoren und Aktoren sind als 
Software-Mockups simuliert.

## Voraussetzungen
- **Mosquitto** als MQTT-Broker, muss im `PATH` sein
  - macOS: `brew install mosquitto`
- Python-Abhängigkeiten aus `requirements.txt`

## Installation

```bash
cd smart_home_secure_demo
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 1. Einmalige Einrichtung (CA, Zertifikate, Onboarding)

```bash
./setup_demo.sh
```

Das Skript legt die CA an, stellt für alle Demo-Geräte Zertifikate aus,
führt das Onboarding über den Commissioner durch und finalisiert die Session-Keys.

## 2. Demo starten

```bash
./run_demo.sh
```

Startet den Broker und alle Komponenten (Hub-Dienste, Sensoren, Aktoren,
HTTP-Wetterstation + Gateway, Heartbeats). Beenden mit `Strg+C`. 
Logs je Prozess unter `logs/run/*.log`.

Im Browser öffnen:

- **Dashboard Smart Home:** http://localhost:8080
- **Broker-Sicht:** http://localhost:8080/broker.html

## Was man beobachten kann

- **Verschlüsselung:** Im Dashboard erscheinen Klartext-Messwerte; in der
  Broker-Sicht laufen über dieselbe Leitung nur verschlüsselte Werte.
- **Automation:** Temperatur und Heizung bilden einen Regelkreis;
    Bewegung schaltet Licht, Nacht-Bewegung den Alarm.
- **Fehlertoleranz:** Stoppt man ein Gerät, markiert der Heartbeat-Monitor es nach
  kurzer Zeit als offline; der Rest läuft weiter.

## Angriffs-Demo: Rogue Device

Ein nicht legitimes Gerät versucht sich anzumelden und wird sichtbar abgelehnt.
Drei Szenarien testen je eine Schutzschicht:

```bash
python3 devices/rogue_device.py forged # gefälschte CA  -> CA-Signatur ungültig
python3 devices/rogue_device.py tampered # Inhalt verändert -> Signatur passt nicht
python3 devices/rogue_device.py stolen # Zertifikat geklaut, kein Privatschlüssel 
python3 hub/commissioner.py # Ablehnung + Eintrag in logs/security_events.log
```

## Projektstruktur 

```
ca/            Certificate Authority + ausgestellte Zertifikate
broker/        Mosquitto-Konfiguration + Broker-Observer
hub/           Commissioner, Telemetrie-Empfänger, Automation, Heartbeat-Monitor, Gateway
devices/       simulierte Sensoren/Aktoren, HTTP-Wetterstation, Rogue Device
shared/        Krypto-Hilfsfunktionen, Topic-/Broker-Konfiguration
dashboard/     Web-Dashboard + Broker-Sicht
```
