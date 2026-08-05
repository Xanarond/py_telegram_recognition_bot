#!/bin/bash
set -e

chown -R appuser:appgroup /app/logs /app/data /app/exports 2>/dev/null || true

exec runuser -u appuser -- python main.py
