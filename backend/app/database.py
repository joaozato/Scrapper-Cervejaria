from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    # Reduzido de 20/10: time pequeno, poucas sessões simultâneas de verdade;
    # conexões ociosas reservadas o tempo todo pesam memória tanto no app
    # quanto no Postgres. 5+5 ainda dá folga confortável acima do pico real.
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
