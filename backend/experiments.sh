#!/bin/sh
# Entry point for the `experiments` compose service (see docker-compose.override.yml).
#
#   docker compose run --rm experiments setup            # (re)create DB + load backend/export.json
#   docker compose run --rm experiments signals_validate # run any experiments.<name>
#
# DATABASE_URL (the journal_exp database) and EXPERIMENTS_EMAIL come from compose.
set -e

if [ "$1" = "setup" ]; then
    python - <<'PY'
import asyncio, os, asyncpg

url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
base, name = url.rsplit("/", 1)

async def main():
    conn = await asyncpg.connect(base + "/postgres")
    # Scratch database: setup always starts clean, so re-running it refreshes the data.
    await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    await conn.execute(f'CREATE DATABASE "{name}"')
    print(f"[experiments] (re)created database {name}")
    await conn.close()

asyncio.run(main())
PY
    python dev_bootstrap.py
    exec python import.py "${2:-export.json}"
fi

module="$1"
shift
exec python -m "experiments.$module" "$EXPERIMENTS_EMAIL" "$@"
