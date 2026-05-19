#!/usr/bin/env bash
set -e

set +e
source /opt/openfoam13/etc/bashrc >/dev/null 2>&1
set -e

exec "$@"
