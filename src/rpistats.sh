#!/usr/bin/env bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
source /srv/rpistats/.venv/bin/activate
python3 rpi-mqtt-monitor.py
deactivate
