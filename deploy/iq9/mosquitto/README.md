# IQ9 MQTT broker

The checked-in configuration intentionally enables anonymous access only for the
isolated hackathon LAN. Do not expose port 1883 to the internet.

After basic multi-device communication works, create a Mosquitto password file,
set `allow_anonymous false`, and add a TLS listener on port 8883. Credentials and
certificates must remain outside Git.
