FROM python:3.11-slim

# Set up an unprivileged user
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source with proper ownership
COPY --chown=user:user . .

USER user

EXPOSE 7860
EXPOSE 8000
EXPOSE 10000

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
