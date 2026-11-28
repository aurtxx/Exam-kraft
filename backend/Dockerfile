FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd --system ezexam && useradd --system --gid ezexam ezexam
COPY --chown=ezexam:ezexam . .
USER ezexam
RUN SECRET_KEY=build-dummy-key DEBUG=True python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
