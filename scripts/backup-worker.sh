#!/bin/sh
set -eu

BACKUP_TARGET="${BACKUP_TARGET:-/data/backups}"
BACKUP_SOURCE_HOST="${BACKUP_SOURCE_HOST:-db}"
BACKUP_SOURCE_PORT="${BACKUP_SOURCE_PORT:-5432}"
BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_FILENAME_PREFIX="${BACKUP_FILENAME_PREFIX:-homeschool-hero}"
UPLOAD_DIR="${UPLOAD_DIR:-/data/uploads}"

mkdir -p "${BACKUP_TARGET}"

healthcheck() {
  export PGPASSWORD="${POSTGRES_PASSWORD:-}"
  pg_isready -h "${BACKUP_SOURCE_HOST}" -p "${BACKUP_SOURCE_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1
  test -d "${BACKUP_TARGET}"
  test -w "${BACKUP_TARGET}"
}

backup_once() {
  export PGPASSWORD="${POSTGRES_PASSWORD:-}"
  timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"
  db_backup="${BACKUP_TARGET}/${BACKUP_FILENAME_PREFIX}_${timestamp}_db.sql.gz"
  uploads_backup="${BACKUP_TARGET}/${BACKUP_FILENAME_PREFIX}_${timestamp}_uploads.tar.gz"

  pg_dump \
    --clean \
    --if-exists \
    --host="${BACKUP_SOURCE_HOST}" \
    --port="${BACKUP_SOURCE_PORT}" \
    --username="${POSTGRES_USER}" \
    "${POSTGRES_DB}" | gzip -c > "${db_backup}"

  if [ -d "${UPLOAD_DIR}" ]; then
    tar -czf "${uploads_backup}" -C "${UPLOAD_DIR}" .
  fi

  find "${BACKUP_TARGET}" -maxdepth 1 -type f -name "${BACKUP_FILENAME_PREFIX}_*" -mtime +"${BACKUP_RETENTION_DAYS}" -delete
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${BACKUP_TARGET}/.last-success"
  echo "Backup written to ${db_backup}"
}

loop() {
  trap 'exit 0' INT TERM
  while true; do
    backup_once
    sleep "${BACKUP_INTERVAL_SECONDS}"
  done
}

case "${1:-loop}" in
  once)
    healthcheck
    backup_once
    ;;
  healthcheck)
    healthcheck
    ;;
  loop)
    healthcheck
    loop
    ;;
  *)
    echo "Usage: $0 [once|loop|healthcheck]" >&2
    exit 1
    ;;
esac
