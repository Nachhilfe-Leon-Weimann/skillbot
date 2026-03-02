import logging

from skillcore.db import Database
from sqlalchemy import text

from skillbot.db.models import Base
from skillbot.db.seed_permissions import seed_default_permission_grants

log = logging.getLogger(__name__)


async def setup_database(db: Database) -> None:
    """Ensure required schemas and tables exist"""

    async with db.engine.begin() as conn:
        schemas = set[str]()
        if Base.metadata.schema:
            schemas.add(Base.metadata.schema)

        for table in Base.metadata.tables.values():
            if table.schema:
                schemas.add(table.schema)

        if conn.dialect.name != "sqlite":
            for schema in sorted(schemas):
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await _ensure_student_profiles_party_column(conn)

    await seed_default_permission_grants(db)


async def _ensure_student_profiles_party_column(conn) -> None:
    has_column = await conn.scalar(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'skillbot'
              AND table_name = 'student_profiles'
              AND column_name = 'party_id'
            """
        )
    )

    if not has_column:
        await conn.execute(text("ALTER TABLE skillbot.student_profiles ADD COLUMN party_id uuid"))

    await conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_student_profiles_party_id'
                ) THEN
                    ALTER TABLE skillbot.student_profiles
                    ADD CONSTRAINT uq_student_profiles_party_id UNIQUE (party_id);
                END IF;
            END $$;
            """
        )
    )

    await conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'fk_student_profiles_party_id'
                ) THEN
                    ALTER TABLE skillbot.student_profiles
                    ADD CONSTRAINT fk_student_profiles_party_id
                    FOREIGN KEY (party_id) REFERENCES core.party(id) ON DELETE RESTRICT;
                END IF;
            END $$;
            """
        )
    )

    null_count = await conn.scalar(text("SELECT COUNT(*) FROM skillbot.student_profiles WHERE party_id IS NULL"))
    if null_count == 0:
        await conn.execute(text("ALTER TABLE skillbot.student_profiles ALTER COLUMN party_id SET NOT NULL"))
    else:
        log.warning("student_profiles.party_id could not be set NOT NULL yet", extra={"null_count": null_count})
