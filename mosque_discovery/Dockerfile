FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY discovery ./discovery
COPY tests ./tests
COPY schema.sql ./schema.sql
RUN useradd -m discovery
USER discovery
# default: periodic crawl loop (see README). One-shot: `python -m discovery crawl --once`
CMD ["python", "-m", "discovery", "loop"]
