#!/bin/sh
# Verschlüsseltes Backup von Datenbank UND Dateien (Fotos, PDFs, Zeichnungen).
#
#   BACKUP_PASSPHRASE_FILE=/pfad/zur/passphrase ./scripts/backup.sh /ziel/verzeichnis
#
# Täglich per Cron/Aufgabenplanung des NAS ausführen. Das Ziel sollte ein getrenntes Medium sein
# (externe Platte, zweites NAS) – RAID ist kein Backup. Die Passphrase getrennt vom Backup aufbewahren!
# Wiederherstellung: scripts/restore.sh – und regelmäßig scripts/restore-test.sh ausführen.
set -eu
cd "$(dirname "$0")/.."
target="${1:?Zielverzeichnis angeben}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE setzen}"
[ -r "$BACKUP_PASSPHRASE_FILE" ] || { echo "Passphrase-Datei nicht lesbar" >&2; exit 1; }
mkdir -p "$target"
stamp="$(date +%Y-%m-%d_%H%M)"
db_file="$target/physioflow-db-$stamp.sql.gz.gpg"
files_file="$target/physioflow-files-$stamp.tar.gz.gpg"
encrypt() { gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase-file "$BACKUP_PASSPHRASE_FILE" -o "$1"; }

docker compose exec -T db pg_dump -U physioflow --clean --if-exists physioflow | gzip | encrypt "$db_file"
docker compose exec -T app tar -C /app/data -cf - . | gzip | encrypt "$files_file"

# Plausibilitätsprüfung: Dateien dürfen nicht leer sein und müssen sich entschlüsseln lassen
for f in "$db_file" "$files_file"; do
  gpg --batch --quiet --passphrase-file "$BACKUP_PASSPHRASE_FILE" -d "$f" | gunzip | head -c 1 >/dev/null \
    || { echo "Backup $f ist nicht lesbar!" >&2; exit 1; }
done
(cd "$target" && sha256sum "$(basename "$db_file")" "$(basename "$files_file")" > "physioflow-$stamp.sha256")

docker compose exec -T app python -m app.cli backup-done "$(basename "$db_file")" >/dev/null
echo "Backup geschrieben: $db_file und $files_file"
# Backups älter als 90 Tage entfernen
find "$target" \( -name 'physioflow-db-*.gpg' -o -name 'physioflow-files-*.gpg' -o -name 'physioflow-*.sha256' \) -mtime +90 -delete
