# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /code

# Install system dependencies (needed for psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .


# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app source code
COPY ./app /code/app

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
