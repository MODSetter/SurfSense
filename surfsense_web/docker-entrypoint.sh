#!/bin/sh
set -e

node /app/docker-entrypoint.js

exec node server.js
