# 137. Schema bootstrap: handle an empty `alembic_version` table

## The bug

`sync_schema` (feature 131) decided stamp-vs-upgrade with
`inspect(engine).has_table("alembic_version")`. On a real user database the
`alembic_version` **table existed but held no row** — the residue of an
earlier startup that got as far as creating the table but not writing the
revision. `has_table` returned `True`, so `sync_schema` ran
`alembic upgrade head`; Alembic saw the current revision as `None`, treated
the DB as being at base, and executed migration `0001`'s `op.create_table`
for the nine story tables — which `create_all()` had **just created** on
the line above. Startup crashed with `table story_channel already exists`,
and the whole app (not just the Studio) failed to boot.

## The fix

Decide on the **recorded revision**, not the table's existence:

```python
recorded = current_revision(engine)   # None if no table OR an empty table
if recorded is None:
    command.stamp(cfg, "head")        # create_all already produced the schema
else:
    command.upgrade(cfg, "head")      # a genuinely older DB catches up
```

`current_revision` (already in the module) uses
`MigrationContext.get_current_revision()`, which returns `None` for both
"no table" and "table present but empty" — so both fresh-DB shapes now
take the stamp path, and only a DB with a real recorded revision is ever
upgraded. `_has_alembic_version` is removed.

## Key files

`app/db/schema.py`; test
`tests/modules/story/test_schema_bootstrap.py::test_empty_alembic_version_table_is_stamped_not_upgraded`.

## Verification

The new test deletes the `alembic_version` row after a normal sync and
re-runs `sync_schema` — it must not raise and must end stamped at
`0001`. Confirmed live: the affected database (49 tables, empty
`alembic_version`, pre-feature-131 `series`) now boots — `create_all`
adds the 9 story tables, `run_additive_column_migrations` adds the 5
`series` studio columns, Alembic stamps `0001`, and `GET /stories`
returns `200`.

## Landed in

`cb06e3d`
