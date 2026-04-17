import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    db_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    if "ssl=require" in db_url:
        db_url = db_url.replace("ssl=require", "sslmode=require")
    engine = create_async_engine(db_url)
    print(f"Connecting to {db_url} using SQLAlchemy async psycopg")
    try:
        async with engine.begin() as conn:
            res = await conn.execute(text("SELECT 1"))
            print(f"SUCCESS! Result: {res.scalar()}")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
