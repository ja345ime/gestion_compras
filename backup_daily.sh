#!/bin/bash
DATE=$(date +%Y%m%d_%H%M)
BACKUP_FILE="backup_$DATE.sql"
pg_dump $DATABASE_URL > "${BACKUP_FILE}"
if [ $? -eq 0 ]; then
    echo "Backup ${BACKUP_FILE} creado" >> backup.log
else
    echo "Fallo al crear backup ${BACKUP_FILE}" >> backup.log
fi
