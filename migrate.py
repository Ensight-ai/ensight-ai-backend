"""Minimal database migration runner.

Applies the SQL files in ``supabase/migrations/`` to the database in order,
tracking which have run in a ``schema_migrations`` table — so each migration
runs exactly once. No external CLI needed.

Usage:
    uv run migrate.py            # apply any new migrations
    uv run migrate.py new <name> # scaffold a new timestamped migration file

Requires DATABASE_URL in the environment / .env — copy it from
Supabase > Project Settings > Database > Connection string (URI).
"""

import datetime
import os
import pathlib
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = pathlib.Path(__file__).parent / "supabase" / "migrations"


def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit(
            "DATABASE_URL is not set.\n"
            "Copy it from Supabase > Project Settings > Database > "
            "Connection string (URI) and put it in your .env."
        )
    # Supabase requires TLS; add it if the URL didn't already specify it.
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return psycopg2.connect(url)


def _applied_versions(cur) -> set[str]:
    cur.execute(
        "create table if not exists schema_migrations ("
        " version text primary key,"
        " applied_at timestamptz not null default now())"
    )
    cur.execute("select version from schema_migrations")
    return {row[0] for row in cur.fetchall()}


def apply_migrations() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("No migration files found in", MIGRATIONS_DIR)
        return

    conn = _connect()
    try:
        with conn.cursor() as cur:
            applied = _applied_versions(cur)
        conn.commit()

        new = 0
        for path in files:
            version = path.name
            if version in applied:
                print(f"  skip   {version}")
                continue
            sql = path.read_text()
            with conn.cursor() as cur:
                cur.execute(sql)  # whole file (may be many statements)
                cur.execute(
                    "insert into schema_migrations (version) values (%s)",
                    (version,),
                )
            conn.commit()  # each migration commits on its own
            print(f"  apply  {version}")
            new += 1

        print(f"Done. {new} new migration(s) applied.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def new_migration(name: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    slug = name.strip().lower().replace(" ", "_")
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = MIGRATIONS_DIR / f"{timestamp}_{slug}.sql"
    path.write_text(f"-- {name}\n\n")
    print("Created", path)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "new":
        if len(args) < 2:
            sys.exit("usage: uv run migrate.py new <name>")
        new_migration(" ".join(args[1:]))
    else:
        apply_migrations()
