#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"

docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:?set POSTGRES_USER}" "${POSTGRES_DB:?set POSTGRES_DB}" \
  > "$BACKUP_DIR/postgres-$STAMP.sql"

docker run --rm \
  -v "$(basename "$(pwd)")_uploads_data:/uploads:ro" \
  -v "$(pwd)/$BACKUP_DIR:/backup" \
  alpine:3.20 \
  tar -czf "/backup/uploads-$STAMP.tar.gz" -C /uploads .

find "$BACKUP_DIR" -type f -mtime +"${BACKUP_RETENTION_DAYS:-14}" -delete

echo "Backup written to $BACKUP_DIR with timestamp $STAMP"
