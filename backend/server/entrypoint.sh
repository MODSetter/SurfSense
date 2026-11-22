#!/bin/sh
# Starts a virtual display when a plugin wants a headed browser (TikTok's profile
# feeds, withheld from headless Chromium), then hands the process to the backend.
set -e
if [ "$(echo "${CRAWL_HEADED_XVFB_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
    display="${XVFB_DISPLAY:-:99}"
    Xvfb "$display" -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 &
    export DISPLAY="$display"
fi
exec python -m server
