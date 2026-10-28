#!/bin/sh
# Wiederherstellungstest: spielt das neueste Backup in eine WEGWERF-Datenbank ein und prüft es
# (Schema, Dateien mit Prüfsummen, Rechnungsnummern). Das laufende System bleibt unberührt.
# Bei Erfolg wird der Test im System vermerkt (Anzeige unter Verwaltung > Betrieb).
#
#   BACKUP_PASSPHRASE_FILE=/pfad/zur/passphrase ./scripts/restore-test.sh /backup/verzeichnis
# Empfehlung: mindestens vierteljährlich, nach größeren Änderungen immer.
set -eu
cd "$(dirname "$0")/.."
dir="${1:?Backup-Verzeichnis angeben}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE setzen}"
db_backup="$(ls -1t "$dir"/physioflow-db-*.gpg 2>/dev/null | head -n 1)"
files_backup="$(ls -1t "$dir"/physioflow-files-*.gpg 2>/dev/null | head -n 1)"
[ -n "$db_backup" ] && [ -n "$files_backup" ] || { echo "Keine Backups in $dir gefunden" >&2; exit 1; }
echo "Teste: $(basename "$db_backup") und $(basename "$files_backup")"

work="$(mktemp -d)"
name="physioflow-restore-test-$$"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT INT TERM
decrypt() { gpg --batch --quiet --passphrase-file "$BACKUP_PASSPHRASE_FILE" -d "$1"; }

docker run -d --name "$name" -e POSTGRES_PASSWORD=restoretest -e POSTGRES_DB=physioflow postgres:16-alpine >/dev/null
i=0
until docker exec "$name" pg_isready -U postgres -d physioflow -q; do
  i=$((i + 1)); [ "$i" -lt 60 ] || { echo "Test-Datenbank startet nicht" >&2; exit 1; }
  sleep 1
done
sleep 2
decrypt "$db_backup" | gunzip | docker exec -i "$name" psql -U postgres -d physioflow -v ON_ERROR_STOP=1 -q >/dev/null 2>"$work/restore.log" \
  || { echo "Wiederherstellung der Datenbank fehlgeschlagen:" >&2; tail -n 20 "$work/restore.log" >&2; exit 1; }
mkdir "$work/files"
decrypt "$files_backup" | gunzip | tar -xf - -C "$work/files"
chmod -R a+rX "$work/files"

docker compose run --rm --no-deps -T \
  -e PHYSIOFLOW_DATABASE_URL="postgresql+psycopg://postgres:restoretest@localhost:5432/physioflow" \
  --network "container:$name" -v "$work/files:/app/data:ro" \
  --entrypoint python app -m app.cli check-integrity
docker compose exec -T app python -m app.cli restore-test-done >/dev/null
echo "Wiederherstellungstest erfolgreich."
