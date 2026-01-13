FROM python:3.11-slim-bookworm

# Install cron and required system dependencies
RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure scripts are executable
# Fix line endings (CRLF -> LF) for Windows compatibility
RUN sed -i 's/\r$//' entrypoint.sh scripts/*.sh && \
    chmod +x entrypoint.sh scripts/*.sh

# Setup Cron
# Create a cron job file
# Run at 18:00 (6 PM) every day
RUN echo "0 18 * * * cd /app && ./scripts/daily_sync.sh >> /var/log/cron.log 2>&1" > /etc/cron.d/nav-cron

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/nav-cron

# Apply cron job
RUN crontab /etc/cron.d/nav-cron

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# Copy entrypoint
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Default command
ENTRYPOINT ["./entrypoint.sh"]
CMD ["cron"]
