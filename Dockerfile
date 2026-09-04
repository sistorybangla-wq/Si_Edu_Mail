FROM python:3.11-slim

# Chrome install
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER=/usr/bin/chromedriver

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Expose port for health check
EXPOSE 8080

# Run both health check and bot
CMD ["python", "-c", "import threading; import subprocess; import time; t1 = threading.Thread(target=lambda: subprocess.run(['python', 'app.py'])); t1.start(); time.sleep(2); subprocess.run(['python', 'main.py'])"]
