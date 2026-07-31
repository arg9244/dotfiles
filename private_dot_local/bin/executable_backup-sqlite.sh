#!/bin/bash
set -euo pipefail

BACKUP_DIR="/media/D/Backup/Linux"
MAX_BACKUPS=5

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

sqlite3 /home/reza/.local/share/komikku/komikku.db ".backup $TMP_DIR/komikku.db"
sqlite3 /home/reza/.config/Throne/config/throne.db ".backup $TMP_DIR/throne.db"

CURRENT_CHECKSUM=$(md5sum "$TMP_DIR/komikku.db" "$TMP_DIR/throne.db" | sort | md5sum | awk '{print $1}')
LAST_CHECKSUM_FILE="$BACKUP_DIR/.last_checksum"
LAST_CHECKSUM=$(cat "$LAST_CHECKSUM_FILE" 2>/dev/null || true)

if [ "$CURRENT_CHECKSUM" = "$LAST_CHECKSUM" ] && [ -n "$LAST_CHECKSUM" ]; then
    exit 0
fi

ARCHIVE_NAME="sqlite_backup_${TIMESTAMP}.tar.gz"
tar -czf "$BACKUP_DIR/$ARCHIVE_NAME" -C "$TMP_DIR" komikku.db throne.db
echo "$CURRENT_CHECKSUM" > "$LAST_CHECKSUM_FILE"

ls -t "$BACKUP_DIR"/sqlite_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
