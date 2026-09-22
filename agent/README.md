# Phase 2 — The LangGraph Agent

Two nodes. `investigator` gathers evidence (Loki logs, Prometheus restart
count, pod describe). `reporter` turns that into a Markdown report with a
likely cause, cited evidence, and one read-only next diagnostic step —
never an automatic fix. See `app/graph.py` for why this file is
deliberately tiny.

## Running it without a live EKS cluster (Codespaces-friendly)

Here's the path that needs zero local installs:

1. **Ollama, in-container:** `docker run -d -p 11434:11434 --name ollama ollama/ollama`
   then `docker exec ollama ollama pull llama3.1:8b`. This satisfies
   `OLLAMA_BASE_URL=http://localhost:11434` in `.env.example` without
   installing Ollama on the Codespace host itself.
2. **kind, in-container, for a throwaway cluster to test against** (instead
   of your real EKS cluster, so you don't need AWS credentials just to
   smoke-test the graph): `kind create cluster`. Deploy a tiny fake
   `httpbin` namespace with `incident-scenario/broken-deployment.yaml` to
   get a real CrashLoopBackOff pod to query against.
3. Run the agent itself directly with `uvicorn`  rather than building the Docker image yet — faster
   iteration: `pip install -r requirements.txt && uvicorn app.main:app --reload`.
4. `curl` a synthetic Alertmanager payload at `/webhook/alertmanager` (see
   below) to trigger a run without needing Alertmanager itself running.

```bash
curl -X POST localhost:8080/webhook/alertmanager \
  -H 'Content-Type: application/json' \
  -d '{
    "alerts": [{
      "labels": {"alertname": "PodCrashLoopBackOff", "namespace": "httpbin", "pod": "crashy-demo-xxxxx", "container": "crashy"},
      "annotations": {"summary": "test", "description": "test alert"},
      "startsAt": "2026-01-01T00:00:00Z"
    }]
  }'
```

Once this works end-to-end against `kind`, redeploying against your real
EKS cluster is just pointing the env vars at the real Loki/Prometheus/
Alertmanager Service DNS names — no code changes.

## Status

Code-complete, not yet run against a live cluster or a real fired alert.
The Phase 2 checkpoint (a real captured alert + the agent's resulting
summary, saved permanently) still needs you to actually trigger the
scenario once — see `docs/incidents/EXAMPLE-RUN-TEMPLATE.md` for where
that goes when you do.
