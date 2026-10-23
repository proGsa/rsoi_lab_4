#!/usr/bin/env bash
set -e

# TODO для создания баз прописать свой вариант
export VARIANT="v4"
export SCRIPT_PATH=/docker-entrypoint-initdb.d/
export PGPASSWORD=postgres
psql -f "$SCRIPT_PATH/scripts/db-$VARIANT.sql"

psql -d libraries -f "$SCRIPT_PATH/scripts/libraries.sql"
psql -d reservations -f "$SCRIPT_PATH/scripts/reservations.sql"
psql -d ratings -f "$SCRIPT_PATH/scripts/ratings.sql"