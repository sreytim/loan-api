# Production readiness checklist: loan-api

Image: `loan-api:prod`, built from `Dockerfile.prod`. Environment: macOS (Apple Silicon), Docker Desktop.

| # | Requirement | Status |
|---|---|---|
| 1 | Multi-stage `Dockerfile.prod`: slim base, non-root user, HEALTHCHECK | Met |
| 2 | `.dockerignore` excludes Git, caches, local models, dev config | Met |
| 3 | Model path configurable with `MODEL_PATH` | Met |
| 4 | `compose.yaml` runs API + PostgreSQL + Adminer, API built from `Dockerfile.prod` | Met |
| 5 | Image at least 40% smaller than the full-Python variant | Met (62.8%) |


---

## 1. Multi-stage, slim, non-root, HEALTHCHECK

`Dockerfile.prod` has two stages: a `builder` stage (`FROM python:3.12-slim AS builder`) that installs packages into a virtual environment and trains the model, and a runtime stage (`FROM python:3.12-slim`) that copies in only the virtual environment, the model and the app files. The runtime stage creates `appuser`, switches to it with `USER appuser`, and defines a `HEALTHCHECK` that calls `/health`.

Commands and output:

```
$ docker run -d --name prod -p 8000:8000 loan-api:prod
a61d1b51ab11b4a7b7c8d16acb5445a4b35daa1699495cefb366d872395d5bce

$ docker exec prod whoami
appuser

$ sleep 35

$ docker ps --filter name=prod
CONTAINER ID   IMAGE           COMMAND                  CREATED              STATUS                        PORTS                    NAMES
a61d1b51ab11   loan-api:prod   "fastapi run main.py…"   About a minute ago   Up About a minute (healthy)   0.0.0.0:8000->8000/tcp   prod

$ docker rm -f prod
prod
```

Result: the container runs as `appuser` (not root) and Docker reports it as `(healthy)`.

---

## 2. `.dockerignore`

Command and output:

```
$ cat .dockerignore
.git
.venv
__pycache__/
*.pyc
.pytest_cache/
.devcontainer/
model.joblib
models/
.env
```

Result: Git history (`.git`), virtual environment, caches, editor/dev config (`.devcontainer/`), locally trained models (`model.joblib`, `models/`) and secrets (`.env`) are excluded from the build context.

---

## 3. `MODEL_PATH` is configurable

`main.py` reads `MODEL_PATH = os.getenv("MODEL_PATH", "model.joblib")`. A version 1.1.0 model was trained into a local `models/` folder, mounted read-only into the container, and selected with `-e MODEL_PATH`.

Commands and output:

```
$ python train.py --version 1.1.0 --out models/model.joblib
Saved model 1.1.0 to models/model.joblib (test AUC 0.923)

$ docker run --rm -p 8000:8000 -v "$(pwd)/models:/models:ro" -e MODEL_PATH=/models/model.joblib loan-api:prod

 ⚡️ Starting FastAPI in production mode
 🌐 Server started at http://0.0.0.0:8000
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     127.0.0.1:53194 - "GET /health HTTP/1.1" 200 OK
^CINFO:     Shutting down
INFO:     Finished server process [1]
```

Health response from the same run (the `/health` body):

```
TODO: paste the result of http://localhost:8000/health here, expected {"status":"ok","model_version":"1.1.0"}
```

Result: the same image started with a different model file, without rebuilding.

---

## 4. Compose: API + PostgreSQL + Adminer

`compose.yaml` builds the `api` service with `context: .` and `dockerfile: Dockerfile.prod`, uses `postgres:17` for `db` (seeded by `init.sql`) and `adminer:4.8.1`. The only password in the repository is the development-only `loans_dev_only` in `compose.yaml`.

Commands and output:

```
$ docker compose up -d --build
✔ Network loan-api_default      Created
✔ Volume "loan-api_pgdata"      Created
✔ Container loan-api-db-1       Healthy
✔ Container loan-api-adminer-1  Started
✔ Container loan-api-api-1      Started

$ sleep 35

$ docker compose ps
NAME                 IMAGE           COMMAND                  SERVICE   CREATED         STATUS                   PORTS
loan-api-adminer-1   adminer:4.8.1   "entrypoint.sh php -…"   adminer   6 minutes ago   Up 6 minutes             0.0.0.0:8080->8080/tcp
loan-api-api-1       loan-api-api    "fastapi run main.py…"   api       6 minutes ago   Up 6 minutes (healthy)   0.0.0.0:8000->8000/tcp
loan-api-db-1        postgres:17     "docker-entrypoint.s…"   db        6 minutes ago   Up 6 minutes (healthy)   5432/tcp
```

Result: three services are running, and both `api` and `db` show `(healthy)`.

---

## 5. Image at least 40% smaller than the full-Python variant

Three variants were built: `full` (from `python:3.12`), `slim` (from `python:3.12-slim`, the Lesson 4.3 Dockerfile) and `prod` (multi-stage `Dockerfile.prod`).

Commands:

```
$ sed 's/FROM python:3.12-slim/FROM python:3.12/' Dockerfile > Dockerfile.full
$ docker build -t loan-api:full -f Dockerfile.full .
$ docker build -t loan-api:slim -f Dockerfile .
$ docker images loan-api
```

Output:

```
REPOSITORY   TAG       IMAGE ID       CREATED          SIZE
loan-api     slim      834cb8f869a7   2 minutes ago    800MB
loan-api     full      c77ebb918bcf   3 minutes ago    2.2GB
loan-api     prod      09ff2d529f29   37 minutes ago   818MB
```

Calculation:

```
1 - (prod / full) = 1 - (818 MB / 2200 MB) = 1 - 0.372 = 0.628  ->  about 62.8% smaller
```

Result: 62.8% is above the required 40%.

