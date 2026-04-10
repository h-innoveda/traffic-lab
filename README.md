# 🚦 Traffic Lab

A hands-on observability playground — send HTTP traffic through Nginx to 3 Flask replicas, watch every request appear in Grafana dashboards powered by Loki logs.

```
Browser UI → Nginx (load balancer) → Flask app-1 / app-2 / app-3
                                          ↓ JSON logs
                                       Promtail → Loki → Grafana
```

---

## Quick Start

### Windows
```bat
cd traffic-lab
start.bat
```

### Linux / macOS
```bash
cd traffic-lab
bash start.sh
```

Both scripts will:
1. Ask for an **Nginx port** (default `1225`)
2. Ask for a **Grafana port** (default `3000`)
3. Check each port is free before accepting it
4. Write a `.env` file and run `docker compose up --build`

Then open:
- **UI Control Panel** → `http://localhost:<nginx-port>`
- **Grafana Dashboards** → `http://localhost:<grafana-port>` (login: `admin` / `admin`)

---

## What's Inside

| Folder / File | What it does |
|---|---|
| `app/main.py` | Flask app — 8 endpoints, structured JSON logging |
| `app/Dockerfile` | Builds the Python image |
| `nginx/nginx.conf` | Load balancer, rate limiting (20 req/s), MIME types |
| `promtail/config.yaml` | Tails log files, ships to Loki with labels |
| `loki/config.yaml` | Log storage, 7-day retention |
| `grafana/provisioning/` | Auto-wires Loki datasource + dashboard on boot |
| `grafana/dashboards/traffic.json` | 13-panel dashboard |
| `ui/` | Control panel (HTML + CSS + JS) |
| `docker-compose.yml` | Wires all services together |
| `kubernetes/` | K8s equivalent of docker-compose |
| `start.sh` | Linux/macOS startup script with port picker |
| `start.bat` | Windows startup script with port picker |

---

## Flask Endpoints

| Endpoint | Behaviour | Use for |
|---|---|---|
| `GET /api/data` | 5–50ms, always 200 | Normal traffic baseline |
| `GET /api/slow` | 1–3 second delay | Latency spike experiments |
| `GET /api/error` | Always 500 | Error rate experiments |
| `GET /api/random-error` | 30% chance of 500 | Flaky service simulation |
| `GET /api/cpu` | Burns CPU ~200ms | CPU load simulation |
| `GET /api/burst` | 5 log lines per request | Log volume experiments |
| `GET /api/replica-info` | Returns pod name/PID | Verify load balancing |
| `GET /health` | Always 200 | Nginx / K8s health probe |

---

## Grafana Dashboard Panels

| Panel | What to watch |
|---|---|
| Total Requests | Overall request count |
| Error Count (5xx) | Spikes when you click "Trigger Error" |
| Active Replicas | Drops when you stop a container |
| Rate Limit Hits (429) | Appears when traffic > 20 req/s |
| Requests/sec by replica | Should be ~equal with round-robin |
| Request rate by endpoint | Which URLs are busiest |
| Status pie chart | 200 vs 429 vs 500 distribution |
| Traffic split % | Load balance fairness per replica |
| Error rate % | SRE golden signal |
| Live log stream | Real-time JSON logs |
| Slow requests (>500ms) | Latency outliers |
| Error logs only | level=ERROR filter |
| Requests/min total | Overall throughput |

---

## Experiments

1. **Kill a replica** — `docker compose stop app-3` → watch "Active Replicas" drop to 2
2. **Hit rate limit** — set Auto Traffic to 25 req/s → 429 errors appear in Grafana
3. **Force errors** — click "Trigger Error" → filter in Grafana: `{app="traffic-lab"} | json | status=500`
4. **Latency spike** — click "Slow Request" → "Slow Requests" panel lights up
5. **Change load balancing** — uncomment `least_conn;` in `nginx/nginx.conf`, restart Nginx
6. **Scale up** — `kubectl scale deployment flask-app --replicas=5 -n traffic-lab` (K8s mode)

---

## Kubernetes (alternative to Docker Compose)

```bash
# Build image first
docker build -t traffic-lab-app:latest ./app

# Apply all manifests
kubectl apply -f kubernetes/

# Access
# UI      → http://localhost:30085
# Grafana → http://localhost:30300
```

---

## LogQL Queries (Grafana Explore)

```logql
# All logs
{app="traffic-lab"} | json

# Only errors
{app="traffic-lab"} | json | status >= 500

# Only one replica
{app="traffic-lab", replica="app-2"} | json

# Slow requests
{app="traffic-lab"} | json | duration_ms > 1000

# Request rate per replica (last 1 min)
sum by (replica) (rate({app="traffic-lab"} | json [1m]))
```

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Ports `1225` and `3000` free (or choose different ones at startup)

---

## Project Structure

```
traffic-lab/
├── docker-compose.yml
├── start.sh              ← Linux/macOS launcher
├── start.bat             ← Windows launcher
├── app/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── nginx/
│   └── nginx.conf
├── promtail/
│   └── config.yaml
├── loki/
│   └── config.yaml
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/loki.yaml
│   │   └── dashboards/dashboard.yaml
│   └── dashboards/
│       └── traffic.json
├── ui/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── kubernetes/
    ├── namespace.yaml
    ├── app-deployment.yaml
    ├── app-service.yaml
    ├── nginx-deployment.yaml
    ├── nginx-service.yaml
    ├── nginx-configmap.yaml
    ├── loki-deployment.yaml
    ├── grafana-deployment.yaml
    └── promtail-daemonset.yaml
```
