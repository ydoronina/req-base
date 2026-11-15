FROM node:22-bookworm-slim AS frontend
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN npm install --global pnpm@11.25.0 && pnpm install --frozen-lockfile
COPY vite.config.js ./
COPY web ./web
RUN pnpm build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY reqbase ./reqbase
COPY static ./static
COPY --from=frontend /app/static/assets ./static/assets
ENV REQBASE_DATA=/data
EXPOSE 8000
CMD ["uvicorn", "reqbase.api:app", "--host", "0.0.0.0", "--port", "8000"]
