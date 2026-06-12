#!/usr/bin/env bash
# Convenience wrapper around `make demo`.
set -euo pipefail
cd "$(dirname "$0")/.."
exec make demo
