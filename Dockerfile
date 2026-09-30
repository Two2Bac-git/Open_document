FROM python:3.12-slim
WORKDIR /app
COPY plow.py indexer.py agent_index_client.py entrypoint.sh ./
# HOME do contêiner: as pastas do usuário são montadas aqui (ex.: /home/plow/Downloads)
ENV HOME=/home/plow \
    PLOW_LOG=/home/plow/.plow/plow.log \
    PLOW_DB=/home/plow/.plow/plow-agent.db \
    AGENT_ID=plow-agent \
    PYTHONUNBUFFERED=1
RUN mkdir -p /home/plow/.plow /home/plow/.agent-index && chmod +x entrypoint.sh
CMD ["/app/entrypoint.sh"]
