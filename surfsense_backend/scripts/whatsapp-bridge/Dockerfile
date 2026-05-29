FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .

ENV WHATSAPP_SESSION_DIR=/data/sessions
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:3000/health || exit 1

CMD ["node", "bridge.js"]
