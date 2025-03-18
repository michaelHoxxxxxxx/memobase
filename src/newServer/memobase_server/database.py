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
Base = declarative_base()
 
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise