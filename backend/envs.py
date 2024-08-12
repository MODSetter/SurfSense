#POSTGRES DB TO TRACK USERS
POSTGRES_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/surfsense"

# API KEY TO VERIFY
API_SECRET_KEY = "surfsense"

# Your JWT secret and algorithm
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720