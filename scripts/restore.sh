#!/bin/sh
# Stellt ein Backup in das laufende System wieder her (ÜBERSCHREIBT alle aktuellen Daten!).
#
#   BACKUP_PASSPHRASE_FILE=/pfad/zur/passphrase ./scripts/restore.sh <physioflow-db-...gpg> <physioflow-files-...gpg>
set -eu
cd "$(dirname "$0")/.."
db_backup="${1:?Datenbank-Backup angeben}"
files_backup="${2:?Datei-Backup angeben}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE setzen}"
echo "ACHTUNG: Alle aktuellen Daten werden durch den Stand des Backups ersetzt."
printf 'Zur Bestätigung WIEDERHERSTELLEN eingeben: '
read -r answer
[ "$answer" = "WIEDERHERSTELLEN" ] || { echo "Abgebrochen."; exit 1; }
decrypt() { gpg --batch --quiet --passphrase-file "$BACKUP_PASSPHRASE_FILE" -d "$1"; }

docker compose stop app
decrypt "$db_backup" | gunzip | docker compose exec -T db psql -U physioflow -d physioflow -v ON_ERROR_STOP=1 -q
decrypt "$files_backup" | gunzip | docker compose run --rm --no-deps -T --entrypoint sh app -c 'find /app/data -mindepth 1 -delete && tar -xf - -C /app/data'
docker compose up -d app
docker compose exec -T app python -m app.cli check-integrity
echo "Wiederherstellung abgeschlossen."
