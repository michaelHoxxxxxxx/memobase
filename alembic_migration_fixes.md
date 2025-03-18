# Alembic迁移问题修复记录

## 问题概述

在执行`alembic upgrade head`命令时，遇到了多个错误，主要涉及以下几个方面：

1. **模块导入错误**：无法找到`memobase_server`模块
2. **PostgresDsn类型处理错误**：SQLAlchemy无法正确处理Pydantic的PostgresDsn类型
3. **异步驱动问题**：使用了异步SQLAlchemy引擎但没有正确配置异步驱动
4. **日志配置错误**：Alembic的日志配置出现`KeyError: 'formatters'`错误
5. **同步/异步环境不匹配**：在同步环境(Alembic)中使用异步SQLAlchemy引擎

## 修复前后代码对比

### 1. 修复模块导入错误

**问题**：Alembic无法找到`memobase_server`模块

#### 修改前 (migrations/env.py)
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from memobase_server.models.user import User  # 导入模型
```

#### 修改后 (migrations/env.py)
```python
from logging.config import fileConfig
import os
import sys

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from memobase_server.models.user import User  # 导入模型
```

### 2. 修复PostgresDsn类型处理错误

**问题**：SQLAlchemy无法直接使用Pydantic的PostgresDsn类型作为数据库URL

#### 修改前 (migrations/env.py)
```python
def run_migrations_offline():
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
```

#### 修改后 (migrations/env.py)
```python
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

def run_migrations_online():
    # 将PostgresDsn对象转换为字符串，并移除asyncpg驱动
    url = str(settings.DATABASE_URL)
    if '+asyncpg' in url:
        url = url.replace('postgresql+asyncpg://', 'postgresql://')
    
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = url
```

### 3. 修复异步驱动问题

**问题**：使用了异步SQLAlchemy引擎但没有正确配置异步驱动

#### 修改前 (memobase_server/database.py)
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from .core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

#### 修改后 (memobase_server/database.py)
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from .core.config import settings

# 将PostgresDsn对象转换为字符串，确保使用asyncpg驱动
db_url = str(settings.DATABASE_URL)
# 如果数据库URL不包含+asyncpg，则添加它
if '+asyncpg' not in db_url:
    db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')

engine = create_async_engine(db_url, echo=settings.DEBUG)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

### 4. 修复日志配置错误

**问题**：Alembic的日志配置出现`KeyError: 'formatters'`错误

#### 修改前 (migrations/env.py)
```python
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
```

#### 修改后 (migrations/env.py)
```python
config = context.config
# 禁用日志配置，避免KeyError: 'formatters'错误
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)
```

### 5. 修复同步/异步环境不匹配问题

**问题**：在同步环境(Alembic)中使用异步SQLAlchemy引擎

#### 尝试方案1：使用异步Alembic (失败)

```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine

async def run_migrations_online():
    # ...
    if isinstance(connectable, AsyncEngine):
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    else:
        with connectable.connect() as connection:
            do_run_migrations(connection)

# ...
asyncio.run(run_migrations_online())
```

#### 最终方案：在Alembic中使用同步SQLAlchemy (成功)

```python
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
```

## 总结

1. **根本原因**：
   - Alembic是同步框架，而我们的应用使用了异步SQLAlchemy
   - Pydantic的PostgresDsn类型需要转换为字符串才能被SQLAlchemy使用
   - 异步SQLAlchemy需要特定的驱动程序(asyncpg)

2. **解决方案**：
   - 在Alembic中使用同步SQLAlchemy，在应用中使用异步SQLAlchemy
   - 将PostgresDsn对象转换为字符串，并根据需要调整驱动程序
   - 禁用Alembic的日志配置，避免格式化器错误

3. **最佳实践**：
   - 在同步环境中使用同步SQLAlchemy
   - 在异步环境中使用异步SQLAlchemy
   - 确保数据库URL格式与所选驱动程序兼容
   - 使用环境变量管理数据库连接信息
