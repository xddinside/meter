#!/bin/bash
export DISPLAY=${DISPLAY:-:0}
cd "$(dirname "$0")"
exec python main.py "$@"