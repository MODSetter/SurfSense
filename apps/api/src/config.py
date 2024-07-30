import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

# If the environment is Gitpod, the root path will be the workspace cluster host
# If not using gitpod, you can delete this if statement, but keep the else clause
if os.getenv("USER") == "gitpod":
    ROOT_PATH = f"https://8000-cording12-nextfastturbo-qqfo0frc496.{os.getenv('GITPOD_WORKSPACE_CLUSTER_HOST')}"
else:
    # Otherwise, the root path will be the local host. ROOT_PATH is an env var configured in Vercel deployment.
    # The value for production is equal to the root path of the deployment URL in Vercel.
    ROOT_PATH = os.getenv("ROOT_PATH", "http://127.0.0.1:8000")


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI App"
    PROJECT_DESCRIPTION: str = "A simple FastAPI app"
    DB_URL: str = os.getenv("DB_URL")
    DB_API_KEY: str = os.getenv("DB_API_KEY")
    DB_EMAIL: str = os.getenv("DB_EMAIL")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    model_config = SettingsConfigDict(env_file=".env")
    API_VERSION: str = "/api/v1"
    ROOT: str = ROOT_PATH


settings = Settings()
