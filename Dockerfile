FROM python:3.10-slim

# Install Node.js 20 (needed for npx @notionhq/notion-mcp-server)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-cache the MCP server package so the first request isn't slow
RUN npx --yes @notionhq/notion-mcp-server --help || true

CMD ["python", "main.py", "serve"]
