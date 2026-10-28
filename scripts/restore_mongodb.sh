#!/usr/bin/env bash
set -euo pipefail

# MongoDB Database Restore Script (Phase 11 Compliance)
# Restores from a specified dump directory.

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <path_to_dump_directory> [database_name]"
    echo "Example: $0 ./backups/20261007_120000 student_dropout_db"
    exit 1
fi

DUMP_PATH="$1"
MONGO_URI="${MONGODB_URI:-mongodb://localhost:27017}"
TARGET_DB="${2:-${MONGODB_DATABASE:-student_dropout_db}}"

if [ ! -d "${DUMP_PATH}" ]; then
    echo "[ERROR] Dump directory does not exist: ${DUMP_PATH}"
    exit 1
fi

echo "[INFO] Restoring database '${TARGET_DB}' from ${DUMP_PATH}..."
mongorestore --uri="${MONGO_URI}" --nsInclude="${TARGET_DB}.*" --gzip "${DUMP_PATH}" --drop

echo "[SUCCESS] Database '${TARGET_DB}' restored successfully."
