import uvicorn
import argparse
import logging
from dotenv import load_dotenv
from app.config.uvicorn import load_uvicorn_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

load_dotenv()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SurfSense application")
    parser.add_argument("--reload", action="store_true", help="Enable hot reloading")
    args = parser.parse_args()

    config = uvicorn.Config(**load_uvicorn_config(args))

    uvicorn.run(config)
