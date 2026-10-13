FROM node:20-alpine AS frontend-build
WORKDIR /build/frontend
ARG VITE_DEMO_MODE=false
ENV VITE_DEMO_MODE=${VITE_DEMO_MODE}
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PYONPYIN_PUBLISHING_ENABLED=false \
    PYONPYIN_GEMINI_AUTOMATION_ENABLED=false \
    PYONPYIN_GITHUB_DISPATCH_ENABLED=false
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY data/ ./data/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN addgroup --system app && adduser --system --ingroup app app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'),timeout=3).read()"
CMD ["sh", "-c", "if [ -z \"$PYONPYIN_ADMIN_PASSWORD\" ] || [ -z \"$PYONPYIN_SESSION_SECRET\" ]; then echo 'Set PYONPYIN_ADMIN_PASSWORD and PYONPYIN_SESSION_SECRET before starting the private preview.' >&2; exit 1; fi; exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60 pyonpyin.web_app:app"]
