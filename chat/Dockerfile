# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install core first (cached layer across backend services)
COPY core /app/core
RUN pip install --no-cache-dir /app/core

# Install chat service
COPY chat /app/chat
RUN pip install --no-cache-dir /app/chat

EXPOSE 8003

CMD ["uvicorn", "normly_chat.main:app", "--host", "0.0.0.0", "--port", "8003"]
