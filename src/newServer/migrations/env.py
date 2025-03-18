from logging.config import fileConfig
import os
import sys

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from memobase_server.models.user import User  # 导入模型
from memobase_server.database import Base
from memobase_server.core.config import settings
 
config = context.config
# 禁用日志配置，避免KeyError: 'formatters'错误
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)
 
target_metadata = Base.metadata
 
def run_migrations_offline():
    # 将PostgresDsn对象转换为字符串，并移除asyncpg驱动
    url = str(settings.DATABASE_URL)
    if '+asyncpg' in url:
        url = url.replace('postgresql+asyncpg://', 'postgresql://')
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
 
    with context.begin_transaction():
        context.run_migrations()
 
def run_migrations_online():
    # 将PostgresDsn对象转换为字符串，并移除asyncpg驱动
    url = str(settings.DATABASE_URL)
    if '+asyncpg' in url:
        url = url.replace('postgresql+asyncpg://', 'postgresql://')
    
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = url
    
    connectable = engine_from_config(
        configuration,
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