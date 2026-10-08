#!/bin/bash
# Entrypoint of the Veda test image: start the Veda setup in the background, then run the normal H3 entrypoint.
mkdir -p /workspace 2>/dev/null
setsid nohup /opt/h3-veda/veda-boot-setup.sh >> /workspace/veda_boot_setup.log 2>&1 < /dev/null &
exec /run-h3.sh "$@"
