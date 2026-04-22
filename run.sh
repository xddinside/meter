#!/bin/bash
export DISPLAY=${DISPLAY:-:0}
cd "$(dirname "$0")"
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
exec python3 -m meter "$@"
