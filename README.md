# Kudos API

Kudos API is a lightweight FastAPI service for sending team recognition and viewing recognition insights through user totals, leaderboard standings, and a recent activity feed.

## Quickstart

### 1) Install dependencies

```bash
python -m pip install --upgrade pip
pip install -e .
```

### 2) Run the API

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

Base URL: `http://localhost:8000`

## API Examples

### POST /kudos

```bash
curl -X POST http://localhost:8000/kudos \
  -H "Content-Type: application/json" \
  -d '{
    "from_user": "alice",
    "to_user": "bob",
    "message": "Great work on the release!"
  }'
```

### GET /kudos/{user}

```bash
curl http://localhost:8000/kudos/bob
```

### GET /leaderboard

```bash
curl http://localhost:8000/leaderboard
```

### GET /recent

```bash
curl http://localhost:8000/recent
```

## Docker

### Build image

```bash
docker build -t kudos-api:latest .
```

### Run container

```bash
docker run --rm -p 8000:8000 kudos-api:latest
```
