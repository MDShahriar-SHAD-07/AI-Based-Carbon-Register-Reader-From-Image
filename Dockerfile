# ---- Base image ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ---- System dependencies for OpenCV ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 libpng16-16 libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

# ---- Set working directory ----
WORKDIR /app

# ---- Install Python dependencies ----
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy backend and frontend ----
COPY server/main.py ./main.py
COPY web/index.html ./index.html

# ---- Expose and run ----
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
