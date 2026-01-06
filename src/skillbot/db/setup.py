from skillcore.db import Database
from sqlalchemy import text

from skillbot.db.models import Base


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
