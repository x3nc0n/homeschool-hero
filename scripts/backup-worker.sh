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

log_event() {
  level="$1"
  action="$2"
  details="$3"
  timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  printf '{"timestamp":"%s","level":"%s","correlation_id":null,"user_id":null,"family_id":null,"action":"%s","details":%s}\n' \
    "${timestamp}" "${level}" "${action}" "${details}"
}

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
  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  log_event "INFO" "backup_started" "{\"target\":\"${BACKUP_TARGET}\",\"started_at\":\"${started_at}\"}"

  if ! pg_dump \
    --clean \
    --if-exists \
    --host="${BACKUP_SOURCE_HOST}" \
    --port="${BACKUP_SOURCE_PORT}" \
    --username="${POSTGRES_USER}" \
    "${POSTGRES_DB}" | gzip -c > "${db_backup}"; then
    log_event "ERROR" "backup_failed" "{\"target\":\"${BACKUP_TARGET}\",\"started_at\":\"${started_at}\",\"reason\":\"database_dump_failed\"}"
    return 1
  fi

  if [ -d "${UPLOAD_DIR}" ] && ! tar -czf "${uploads_backup}" -C "${UPLOAD_DIR}" .; then
    log_event "ERROR" "backup_failed" "{\"target\":\"${BACKUP_TARGET}\",\"started_at\":\"${started_at}\",\"reason\":\"uploads_archive_failed\"}"
    return 1
  fi

  find "${BACKUP_TARGET}" -maxdepth 1 -type f -name "${BACKUP_FILENAME_PREFIX}_*" -mtime +"${BACKUP_RETENTION_DAYS}" -delete
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${BACKUP_TARGET}/.last-success"
  db_size="$(wc -c < "${db_backup}" | tr -d ' ')"
  uploads_size=0
  if [ -f "${uploads_backup}" ]; then
    uploads_size="$(wc -c < "${uploads_backup}" | tr -d ' ')"
  fi
  total_size=$((db_size + uploads_size))
  printf '%s\n' "${total_size}" > "${BACKUP_TARGET}/.last-success-size"
  log_event "INFO" "backup_completed" "{\"target\":\"${BACKUP_TARGET}\",\"started_at\":\"${started_at}\",\"completed_at\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",\"size_bytes\":${total_size}}"
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
