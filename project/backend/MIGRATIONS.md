# Database migrations

Alembic is deliberately isolated from the application's `NEON_DB_URL`.
Every command that connects to a database requires `ALEMBIC_DATABASE_URL`, so a
developer cannot accidentally migrate production merely by loading `.env`.

## Initial normalized schema

Revision `0001_baseline` creates the normalized schema on an **empty** database.
It must not be stamped onto the legacy database: the old `saved_posts` columns
and the new ORM metadata are materially different.

Before rebuilding production:

1. Preserve a backup or Neon restore point even when the old data is disposable.
2. Create an empty Neon branch and run `alembic upgrade head` there.
3. Start the application against that branch and test crawl, save, feed,
   product deletion, and user deletion behavior.
4. Only after validation, reset production through the provider's explicit
   database/branch workflow and run `alembic upgrade head` against the empty DB.

Do not use `alembic stamp` to move the legacy schema to this revision. Stamping
records only a version number and would leave the actual tables incompatible.

## New schema changes

Generate against a disposable branch, review the file, then inspect SQL without
applying it:

```bash
ALEMBIC_DATABASE_URL='postgresql://...' \
  alembic -c project/backend/alembic.ini revision --autogenerate -m 'change description'

ALEMBIC_DATABASE_URL='postgresql://...' \
  alembic -c project/backend/alembic.ini upgrade head --sql
```

Apply first to a disposable branch and then staging. Back up production before
applying the reviewed migration there.

Autogenerate ignores database-only objects and rejects generated table/column
drops. Destructive migrations must be handwritten and explicitly reviewed.
Downgrading the baseline additionally requires `ALEMBIC_ALLOW_DESTRUCTIVE=1` and
must only be done on a disposable database.
