# Migrating existing data from SQLite to PostgreSQL

If you were previously running this backend on SQLite and have real data in
`db.sqlite3` you want to keep (not just the seed data), use this instead of
starting from a fresh `seed_demo_data`.

This exact sequence was tested end-to-end before being written down here:
seeded a SQLite database, added an extra row through the ORM (standing in
for "real" user data), dumped it, loaded it into a fresh Postgres database,
and confirmed both the original and extra data were visible through the
live API afterward — including that a brand-new row created post-migration
got the correct next ID with no collision.

## Steps

**1. While `config/settings.py` still points at SQLite**, export everything:

```bash
python manage.py dumpdata \
  --natural-foreign --natural-primary \
  -e contenttypes -e auth.permission -e admin.logentry -e sessions \
  -e token_blacklist.outstandingtoken -e token_blacklist.blacklistedtoken \
  --indent 2 > data_dump.json
```

The excluded apps are all regenerated automatically by Django and would
either conflict or are pointless to carry over: content types and
permissions get recreated by migrations, `admin.logentry` is just admin-site
history, `sessions` and the JWT blacklist tables are transient — nobody
needs their old login sessions to survive a database migration.

**2. Switch to Postgres** (already done in this project's `config/settings.py`
— see `.env.example` for the `DB_*` variables to set) and create the empty schema:

```bash
pip install -r requirements.txt
createdb vibe_tracker   # or: psql -U postgres -c "CREATE DATABASE vibe_tracker;"
python manage.py migrate
```

**3. Load your data in:**

```bash
python manage.py loaddata data_dump.json
```

That's it. **No manual sequence/ID fixing needed** — Django's `loaddata`
automatically calls `reset_sequences()` after loading, for any database
backend that requires it (PostgreSQL does; that's what makes the next
auto-generated ID come out correct instead of colliding with a row you just
loaded).

## Things to double check

- **Only run `loaddata` once, against a freshly migrated, empty database.**
  Running it twice, or against a database that already has rows, will throw
  duplicate-key errors.
- **Uploaded Documents:** the `Document.file` field only stores a *path* in
  the database — the actual file bytes live in your `media/` folder on disk.
  The dump/load above moves database rows, not files, so make sure your
  `media/` folder comes along too (copy it over, or just keep the project
  directory where it already was).
- **Passwords carry over correctly** — Django stores password hashes (not
  plaintext) on the `accounts.user` rows, and `dumpdata`/`loaddata` preserve
  them exactly, so everyone's existing login still works after migrating.
