FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN groupadd --gid 10001 shopping && useradd --uid 10001 --gid shopping --no-create-home shopping \
    && mkdir -p /app/media /app/staticfiles /app/beat \
    && chown -R shopping:shopping /app
USER shopping
EXPOSE 8000
