from dotenv import load_dotenv
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys

# Load environment variables from .env file
load_dotenv()

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from app.core.database import Base
from app.models.user import User
from app.models.task import Task
from app.models.refresh_token import RefreshToken
from app.models.audit_log import AuditLog

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Get the database URL from the environment and escape the '%' for configparser
db_url = os.getenv('DATABASE_URL')
if db_url:
    # Escape the '%' character for the config parser
    config.set_main_option('sqlalchemy.url', db_url.replace('%', '%%'))
else:
    # Fallback or error if DATABASE_URL is not set
    raise ValueError("DATABASE_URL environment variable not set")


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()