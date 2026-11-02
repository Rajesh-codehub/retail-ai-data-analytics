from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# 1. Import your Pydantic settings and SQLAlchemy Base
from app.core.config import settings
from app.db.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .env file in use.
config = context.config

# 2. Inject your Pydantic DATABASE_URL into Alembic's config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Point target_metadata to your models' Base metadata
target_metadata = Base.metadata