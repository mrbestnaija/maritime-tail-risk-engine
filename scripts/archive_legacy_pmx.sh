#!/usr/bin/env bash
# ==============================================================================
# archive_legacy_pmx.sh: Safe Archival Utility for Legacy portfolio_maximizer Codebase
# ==============================================================================
set -euo pipefail

LEGACY_DIR="${1:-../portfolio_maximizer_v45}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="legacy_pmx_cold_storage_${TIMESTAMP}.tar.gz"
DEST_DIR="${2:-./archive}"

echo "======================================================================"
echo "    LEGACY PMX COLD-STORAGE ARCHIVAL PROTOCOL (Phase 1 Transition)   "
echo "======================================================================"
echo "Source Legacy Path : ${LEGACY_DIR}"
echo "Archive Target     : ${DEST_DIR}/${ARCHIVE_NAME}"

if [ ! -d "${LEGACY_DIR}" ]; then
    echo "ERROR: Legacy directory '${LEGACY_DIR}' not found!" >&2
    exit 1
fi

mkdir -p "${DEST_DIR}"

echo "Compacting legacy codebase (excluding caches and virtual environments)..."
tar --exclude="*__pycache__*" \
    --exclude="*.pytest_cache*" \
    --exclude="*.venv*" \
    --exclude="*node_modules*" \
    --exclude="*.hypothesis*" \
    --exclude="*.git*" \
    --exclude="*.tmp*" \
    -czf "${DEST_DIR}/${ARCHIVE_NAME}" \
    -C "$(dirname "${LEGACY_DIR}")" "$(basename "${LEGACY_DIR}")"

echo "Calculating SHA-256 lineage hash of archive..."
ARCHIVE_SHA256=$(sha256sum "${DEST_DIR}/${ARCHIVE_NAME}" | awk '{print $1}')

echo "======================================================================"
echo "ARCHIVAL COMPLETE"
echo "Archive File : ${DEST_DIR}/${ARCHIVE_NAME}"
echo "SHA-256 Hash : ${ARCHIVE_SHA256}"
echo "======================================================================"
