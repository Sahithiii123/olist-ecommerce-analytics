FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[search,agent]"
ENV PORT=8080
CMD ["sh", "-c", "uvicorn olist_agent.api:app --host 0.0.0.0 --port ${PORT}"]