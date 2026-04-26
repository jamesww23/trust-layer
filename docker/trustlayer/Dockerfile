# Trust-layer node — minimal image for running a self-contained instance
# of the reputation server with the in-memory store.
#
# The server uses only the Python standard library, so this image needs
# no pip install and stays under ~150 MB.  Each container is independent:
# its own state, its own registry, its own trust scores.
#
# Build:   docker build -t trustlayer-node -f docker/trustlayer/Dockerfile .
# Run:     docker run -p 4001:4000 trustlayer-node
# Compose: docker compose up   (boots two nodes — see docker-compose.yml)

FROM python:3.11-slim

WORKDIR /app

# Copy only what server.py actually needs at runtime.
COPY core/    ./core/
COPY public/  ./public/
COPY data/    ./data/
COPY server.py ./server.py

EXPOSE 4000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python3 -c "import urllib.request as u; u.urlopen('http://localhost:4000/api/agents', timeout=2)" || exit 1

CMD ["python3", "server.py", "4000"]
