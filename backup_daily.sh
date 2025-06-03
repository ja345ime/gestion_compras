#!/bin/bash
BACKUP_DIR=${BACKUP_DIR:-/backups}
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql"
if pg_dump "$DATABASE_URL" > "$BACKUP_FILE"; then
    echo "$(date): Backup ${BACKUP_FILE} creado" >> "$BACKUP_DIR/backup.log"
else
    echo "$(date): Fallo al crear backup ${BACKUP_FILE}" >> "$BACKUP_DIR/backup.log"
fi
