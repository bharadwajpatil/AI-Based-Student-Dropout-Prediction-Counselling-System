#!/usr/bin/env bash
set -euo pipefail

# MongoDB Automated Backup Script (Phase 11 Compliance)
# Creates a timestamped, gzip-compressed database dump.

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TARGET_DIR="${BACKUP_DIR}/${TIMESTAMP}"
MONGO_URI="${MONGODB_URI:-mongodb://localhost:27017}"
DATABASE_NAME="${MONGODB_DATABASE:-student_dropout_db}"

mkdir -p "${TARGET_DIR}"

echo "[INFO] Starting database backup for '${DATABASE_NAME}' at ${TIMESTAMP}..."
mongodump --uri="${MONGO_URI}" --db="${DATABASE_NAME}" --out="${TARGET_DIR}" --gzip

echo "[SUCCESS] Backup complete. Stored in: ${TARGET_DIR}"

# Retention Policy: Prune backups older than 30 days
find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
echo "[INFO] Retained recent backups. Older dumps pruned."
