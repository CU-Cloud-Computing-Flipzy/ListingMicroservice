FROM python:3.10-alpine

# Install dependencies
WORKDIR /listing_service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Expose port (FastAPI default)
ENV PORT=8000

# Run the app with Uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]