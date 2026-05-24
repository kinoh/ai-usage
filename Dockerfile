FROM node:24-bookworm-slim

ARG CODEX_VERSION=0.133.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 \
    && npm install -g "@openai/codex@${CODEX_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.npm

WORKDIR /app

COPY src ./src
COPY docker-entrypoint.sh /usr/local/bin/ai-usage-entrypoint

ENV PYTHONPATH=/app/src
ENV CODEX_HOME=/codex-home

RUN chmod +x /usr/local/bin/ai-usage-entrypoint \
    && mkdir -p /codex-home

EXPOSE 9108

ENTRYPOINT ["ai-usage-entrypoint"]
CMD ["exporter"]
