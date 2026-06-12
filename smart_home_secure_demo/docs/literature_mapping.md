# Literature Mapping

## MQTT als Kommunikationsmodell

MQTT wird verwendet, weil es ein leichtgewichtiges Publish Subscribe Protokoll ist, das besonders für IoT und Machine to Machine Kommunikation geeignet ist. Dadurch können Sensoren, Aktoren und Automationsdienste lose gekoppelt kommunizieren.

Quelle:
OASIS MQTT Version 5.0 Standard

## Secure Device Onboarding

Das Onboarding orientiert sich konzeptionell an Matter. Ein neues Gerät wird erst nach Identitätsprüfung in das Netzwerk aufgenommen. Die Rolle des Hubs entspricht vereinfacht einem Commissioner. Die simulierten Geräte entsprechen Commissionees.

Quellen:
Connectivity Standards Alliance Matter
Google Matter Commissioning Dokumentation
Silicon Labs Matter Security Dokumentation

## Geräteidentität 

Jedes legitime Gerät besitzt eine eigene kryptografische Identität. Die Certificate Authority signiert die Geräteinformationen. Der Hub akzeptiert nur Geräte, deren Zertifikat durch die CA verifiziert werden kann.

Quellen:
Matter Device Attestation Konzepte
NISTIR 8259A IoT Device Cybersecurity Capability Core Baseline

## Verschlüsselte Kommunikation

Nach erfolgreichem Onboarding wird ein gemeinsamer Sitzungsschlüssel verwendet. Nutzdaten werden verschlüsselt übertragen, sodass der MQTT Broker nicht als vertrauenswürdige Stelle betrachtet werden muss.

Quellen:
OWASP IoT Project
NIST IoT Cybersecurity Guidance

## Verwendete kryptografische Verfahren

Ed25519 wird für digitale Signaturen genutzt
X25519 wird für den Schlüsselaustausch genutzt
AES GCM wird für authentifizierte symmetrische Verschlüsselung genutzt

Quellen:
RFC 8032
RFC 7748
Python cryptography Dokumentation