#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
CERT_DIR="${PROJECT_ROOT}/nginx/certs"
CERT_NAME="${CERT_NAME:-homeschool-hero}"
HOSTNAME="${CERT_HOSTNAME:-localhost}"
DAYS="${CERT_DAYS:-365}"

mkdir -p "${CERT_DIR}"

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "${CERT_DIR}/${CERT_NAME}.key" \
  -out "${CERT_DIR}/${CERT_NAME}.crt" \
  -days "${DAYS}" \
  -subj "/CN=${HOSTNAME}" \
  -addext "subjectAltName=DNS:${HOSTNAME},DNS:localhost,IP:127.0.0.1"

echo "Generated ${CERT_DIR}/${CERT_NAME}.crt and ${CERT_DIR}/${CERT_NAME}.key"
