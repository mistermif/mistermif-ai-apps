#!/usr/bin/with-contenv bashio
set -e

export KNAUS_DATA_DIR="/data"
export KNAUS_OPTIONS_FILE="/data/options.json"
export KNAUS_HOST="0.0.0.0"
export KNAUS_PORT="8099"

bashio::log.info "Avvio Knaus Copilot..."
exec python3 -m app.main

