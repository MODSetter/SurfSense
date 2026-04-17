import psycopg
import os
from dotenv import load_dotenv

def main():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = db_url.replace("ssl=require", "sslmode=require")
    
    print(f"Connecting to {db_url} using PSYCOPG")
    try:
        with psycopg.connect(db_url) as conn:
            print("SUCCESS: Connected to Neon DB via Psycopg!")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
