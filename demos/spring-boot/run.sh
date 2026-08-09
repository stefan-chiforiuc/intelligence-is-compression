#!/usr/bin/env bash
# Spring Boot: real cold start, real request thread pool.
#   bash demos/spring-boot/run.sh            # both parts (~4 min)
#   bash demos/spring-boot/run.sh --part 1   # cold start only
set -uo pipefail
cd "$(dirname "$0")/../.."
exec python3 demos/spring-boot/run.py "$@"
