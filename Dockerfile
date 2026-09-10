FROM python:3.12-slim

# lbzip2 descomprime los 7 GB del dump en paralelo; bzip2 monohilo tarda ~1h
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates lbzip2 zstd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
# para que `python scripts/xx.py` encuentre const.py sin tocar sys.path
ENV PYTHONPATH=/app

CMD ["bash"]
