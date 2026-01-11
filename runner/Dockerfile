FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git verilator make g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY hwci.py /app/hwci.py

ENTRYPOINT ["python", "/app/hwci.py"]
