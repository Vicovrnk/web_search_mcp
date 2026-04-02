FROM node:22-alpine

ENV NODE_ENV=production

WORKDIR /app

COPY package.json /app/
RUN npm install --omit=dev

COPY server.js /app/

ENV PORT=3010
EXPOSE 3010

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:3010/healthz',(r)=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
