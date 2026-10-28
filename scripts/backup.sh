#!/bin/sh
# Verschlüsseltes Datenbank-Backup. Aufruf z. B. täglich per Cron auf dem NAS:
#   BACKUP_PASSPHRASE_FILE=/pfad/zur/passphrase ./scripts/backup.sh /ziel/verzeichnis
# Das Ziel sollte ein getrenntes Medium sein (externe Platte, zweites NAS) – RAID ist kein Backup.
# Wiederherstellung:
#   gpg -d physioflow-DATUM.sql.gz.gpg | gunzip | docker compose exec -T db psql -U physioflow physioflow
set -eu
cd "$(dirname "$0")/.."
target="${1:?Zielverzeichnis angeben}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE setzen}"
mkdir -p "$target"
file="$target/physioflow-$(date +%Y-%m-%d_%H%M).sql.gz.gpg"
docker compose exec -T db pg_dump -U physioflow --clean --if-exists physioflow \
  | gzip \
  | gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase-file "$BACKUP_PASSPHRASE_FILE" -o "$file"
echo "Backup geschrieben: $file"
# Backups älter als 90 Tage entfernen
find "$target" -name 'physioflow-*.sql.gz.gpg' -mtime +90 -delete
