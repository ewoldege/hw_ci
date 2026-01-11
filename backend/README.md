# HWCI API (Minimal)

## Run locally

```
docker compose up --build
```

## Example usage

Create a run:

```
curl -X POST http://localhost:8000/runs -H "Content-Type: application/json" -d "{}"
```

Upload artifact:

```
curl -X POST http://localhost:8000/runs/<run_id>/artifacts -F "file=@path/to/log.txt"
```

List artifacts:

```
curl http://localhost:8000/runs/<run_id>/artifacts
```

Download link:

```
curl http://localhost:8000/artifacts/<artifact_id>/download
```
