#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" -m venv --system-site-packages --clear "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"

mkdir -p "${ROOT_DIR}/models"

echo
echo "Linux bootstrap complete."
echo "Activate with: source ${VENV_DIR}/bin/activate"
echo "Optional model override: export ATHENA_MODEL_DIR=${ROOT_DIR}/models/Qwen3.5-4B"
