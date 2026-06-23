FROM python:3.11-slim AS api-base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY api/ api/
COPY models/ models/
COPY data/ data/

EXPOSE 8001

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]


FROM node:20-alpine AS web-base

WORKDIR /app

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ .

RUN npm run build

FROM nginx:alpine AS web-prod
COPY --from=web-base /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
