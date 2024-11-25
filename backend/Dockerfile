# Use official Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy backend source code
COPY . /app

# Install dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose backend port
EXPOSE 8000

# Run FastAPI using uvicorn
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
