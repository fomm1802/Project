# Project

## Run in one command (Linux/macOS)
```bash
./run.sh
```

## Run in one command (Windows)
```bat
Run.bat
```

## Extra commands
```bash
python -m py_compile bot.py utils.py web/__init__.py web/api.py cogs/commands/invite_all.py
python benchmarks/benchmark_concurrency.py
```


## Render deployment note
- Set Start Command to `./run.sh`
- Open your service URL to go directly to the dashboard (`/`)
- API status endpoint is now `/api` and health check is `/healthz`
