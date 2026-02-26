FROM python:3.13-slim

WORKDIR /app

# Keep it minimal for now
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Code will be bind-mounted at runtime (Option B), but copy anyway for build completeness
COPY . /app