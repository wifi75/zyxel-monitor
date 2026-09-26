# --- build frontend ---
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- runtime ---
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends snmp tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# produttori dal MAC (elenco pubblico IEEE); se il sito non risponde la build prosegue senza
RUN python -c "import urllib.request as u; r=u.Request('https://standards-oui.ieee.org/oui/oui.csv', headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36', 'Accept': 'text/csv,*/*'}); open('oui.csv','wb').write(u.urlopen(r, timeout=60).read())"     || echo "oui.csv non scaricato: produttori non disponibili"
COPY backend/app ./app
COPY --from=web /web/dist ./static
ENV DB_PATH=/data/monitor.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
