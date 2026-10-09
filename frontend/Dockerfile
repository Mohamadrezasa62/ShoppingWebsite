FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
RUN cp -r .next/static .next/standalone/.next/static && if [ -d public ]; then cp -r public .next/standalone/public; fi

EXPOSE 3000
ENV NODE_ENV=production
CMD ["node", ".next/standalone/server.js"]
