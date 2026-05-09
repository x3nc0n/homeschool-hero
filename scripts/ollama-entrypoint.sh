#!/bin/sh
set -eu

ollama serve &
ollama_pid="$!"

cleanup() {
  kill "${ollama_pid}" >/dev/null 2>&1 || true
  wait "${ollama_pid}" >/dev/null 2>&1 || true
}

trap cleanup INT TERM

until ollama list >/dev/null 2>&1; do
  sleep 2
done

if [ -n "${OLLAMA_MODEL:-}" ]; then
  ollama pull "${OLLAMA_MODEL}"
fi

wait "${ollama_pid}"
