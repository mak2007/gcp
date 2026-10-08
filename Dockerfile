FROM python:3.13-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Ensure /data exists and is writable for persistent storage
RUN mkdir -p /data && chmod 777 /data

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Run the bot
CMD ["python", "bot.py"]
