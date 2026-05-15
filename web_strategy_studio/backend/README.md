Backend package for Web Strategy Studio. See the parent [`../README.md`](../README.md) for full setup.

## Database Migrations (Alembic — B19)

### First-time setup

```bash
cd web_strategy_studio/backend
pip install -e ".[dev]"
# For PostgreSQL production, set EQ_STUDIO_DATABASE_URL first:
export EQ_STUDIO_DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
alembic upgrade head
```

### Writing a migration

1. Edit the models in `studio_api/models.py`.
2. Auto-generate a migration:
   ```bash
   alembic revision --autogenerate -m "describe your change"
   ```
3. Review and edit the generated file in `alembic/versions/`.
4. Apply it:
   ```bash
   alembic upgrade head
   ```
5. To roll back one step:
   ```bash
   alembic downgrade -1
   ```

### Notes

* The app uses `SQLAlchemy + aiosqlite` for async access; Alembic runs with a
  **synchronous** connection (no `+aiosqlite` prefix) — this is handled automatically
  by `alembic/env.py`.
* All migrations are PG-compatible: use `sa.String`, `sa.Text`, `sa.DateTime(timezone=True)`,
  `sa.JSON` — never SQLite-specific pragmas.
* Development and test environments still use `create_all` for speed; run
  `alembic upgrade head` only on staging/production Postgres instances.
