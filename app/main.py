"""
main.py — The Flask application (heart of the whole system)

This file does 3 things:
  1. Serves HTTP endpoints that the UI calls
  2. Simulates real-world behaviors (slow responses, errors, CPU load)
  3. Writes structured JSON logs so Grafana can query them later

WHY STRUCTURED LOGGING?
  Plain log:      "Request received from 127.0.0.1"
  Structured log: {"level":"info","status":200,"duration_ms":12,"path":"/api/data","replica":"app-1"}
  
  Structured = every field is a key-value pair → Loki can filter by status=500
  Plain text = you'd have to regex-parse it → slow and fragile
"""

import os
import time
import random
import logging
import json
import math
from flask import Flask, jsonify, request
from flask_cors import CORS

# ─────────────────────────────────────────────
# STRUCTURED LOGGER SETUP
# ─────────────────────────────────────────────
# We build a custom JSON formatter so every log line is valid JSON.
# Loki will ingest these lines and Grafana can query fields like:
#   {app="traffic-lab"} | json | status >= 400

class JSONFormatter(logging.Formatter):
    """Converts every log record into a single-line JSON string."""
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),   # when it happened
            "level":     record.levelname,           # INFO / WARNING / ERROR
            "message":   record.getMessage(),        # the actual message
            "logger":    record.name,                # which logger emitted it
        }
        # Merge any extra fields passed via extra={...} in the log call
        for key, value in record.__dict__.items():
            if key not in ("msg", "args", "levelname", "levelno", "pathname",
                           "filename", "module", "exc_info", "exc_text",
                           "stack_info", "lineno", "funcName", "created",
                           "msecs", "relativeCreated", "thread", "threadName",
                           "processName", "process", "name", "message",
                           "taskName", "asctime"):
                log_entry[key] = value
        return json.dumps(log_entry)

# Create the logger
logger = logging.getLogger("traffic-lab")
logger.setLevel(logging.DEBUG)

# Write logs to STDOUT (Docker captures stdout → Promtail reads it)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Also write to a file so Promtail can tail it inside the container
os.makedirs("/app/logs", exist_ok=True)
file_handler = logging.FileHandler("/app/logs/app.log")
file_handler.setFormatter(JSONFormatter())
logger.addHandler(file_handler)

# ─────────────────────────────────────────────
# FLASK APP SETUP
# ─────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # Allow the UI (different origin) to call this API

# REPLICA_ID: each container gets a unique name via environment variable.
# Docker Compose sets this to "app-1", "app-2", "app-3"
# This is how Grafana shows WHICH replica handled each request.
REPLICA_ID = os.environ.get("REPLICA_ID", "app-unknown")

# ─────────────────────────────────────────────
# HELPER: log every request with timing
# ─────────────────────────────────────────────
def log_request(path, status, duration_ms, extra=None):
    """
    Central logging function. Every endpoint calls this.
    
    Fields logged (all queryable in Grafana):
      - replica:     which app instance handled it  → filter by replica="app-2"
      - path:        which endpoint was called       → filter by path="/api/slow"
      - status:      HTTP status code                → filter by status >= 400
      - duration_ms: how long it took                → build latency histograms
      - method:      GET / POST                      → filter by method
      - client_ip:   who sent the request
    """
    log_data = {
        "replica":     REPLICA_ID,
        "path":        path,
        "status":      status,
        "duration_ms": round(duration_ms, 2),
        "method":      request.method,
        "client_ip":   request.remote_addr,
    }
    if extra:
        log_data.update(extra)  # merge any endpoint-specific fields

    # Choose log level based on HTTP status code
    if status >= 500:
        logger.error("request completed", extra=log_data)
    elif status >= 400:
        logger.warning("request completed", extra=log_data)
    else:
        logger.info("request completed", extra=log_data)


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/health")
def health():
    """
    Health check endpoint.
    Nginx uses this to decide if a replica is alive.
    Kubernetes liveness probe also hits this.
    Returns: {"status": "ok", "replica": "app-1"}
    """
    start = time.time()
    response = {"status": "ok", "replica": REPLICA_ID}
    log_request("/health", 200, (time.time() - start) * 1000)
    return jsonify(response), 200


@app.route("/api/data")
def normal_request():
    """
    Normal fast request — simulates a typical API call.
    
    Adds a tiny random delay (5–50ms) to simulate real DB/network latency.
    This is the endpoint the UI's "Normal Traffic" button hammers.
    
    EXPERIMENT: Watch Grafana's request rate panel spike when you click burst.
    """
    start = time.time()
    
    # Simulate realistic latency (5ms to 50ms)
    time.sleep(random.uniform(0.005, 0.05))
    
    response = {
        "replica": REPLICA_ID,
        "data":    "some payload",
        "ts":      time.time(),
    }
    duration = (time.time() - start) * 1000
    log_request("/api/data", 200, duration)
    return jsonify(response), 200


@app.route("/api/slow")
def slow_request():
    """
    Slow request — simulates a heavy DB query or external API call.
    
    Sleeps 1–3 seconds. Watch the p99 latency panel in Grafana jump.
    
    EXPERIMENT: Send 10 slow requests, see how duration_ms distribution
    changes in the latency histogram panel.
    """
    start = time.time()
    
    # Simulate a slow operation (1 to 3 seconds)
    delay = random.uniform(1.0, 3.0)
    time.sleep(delay)
    
    response = {
        "replica":  REPLICA_ID,
        "delay_ms": round(delay * 1000, 2),
        "message":  "slow operation completed",
    }
    duration = (time.time() - start) * 1000
    log_request("/api/slow", 200, duration, extra={"simulated_delay_ms": round(delay * 1000, 2)})
    return jsonify(response), 200


@app.route("/api/error")
def error_request():
    """
    Forced 500 error — simulates a backend crash or unhandled exception.
    
    EXPERIMENT: Click "Trigger Error" in UI, then in Grafana run:
      {app="traffic-lab"} | json | status=500
    You'll see exactly which replica failed and when.
    """
    start = time.time()
    duration = (time.time() - start) * 1000
    
    log_request("/api/error", 500, duration, extra={"error_type": "simulated_internal_error"})
    return jsonify({
        "error":   "Internal Server Error",
        "replica": REPLICA_ID,
        "message": "This error was intentionally triggered for demo purposes",
    }), 500


@app.route("/api/random-error")
def random_error():
    """
    30% chance of returning a 500 error, 70% chance of success.
    
    Simulates a flaky microservice (e.g., intermittent DB connection issues).
    
    EXPERIMENT: Send 20 requests, watch the error rate panel in Grafana
    hover around 30%. This is how SREs detect reliability regressions.
    """
    start = time.time()
    
    # 30% failure rate
    if random.random() < 0.3:
        duration = (time.time() - start) * 1000
        log_request("/api/random-error", 500, duration, extra={"error_type": "random_failure"})
        return jsonify({"error": "Random failure occurred", "replica": REPLICA_ID}), 500
    
    time.sleep(random.uniform(0.01, 0.1))
    duration = (time.time() - start) * 1000
    log_request("/api/random-error", 200, duration)
    return jsonify({"status": "ok", "replica": REPLICA_ID}), 200


@app.route("/api/cpu")
def cpu_load():
    """
    CPU-intensive endpoint — runs a math loop to burn CPU cycles.
    
    Simulates a compute-heavy operation (image processing, ML inference, etc.)
    
    EXPERIMENT: Hit this endpoint 10 times rapidly, watch Docker stats
    show CPU spike. In production you'd see this in a CPU metrics panel.
    """
    start = time.time()
    
    # Burn CPU for ~200ms by computing square roots in a tight loop
    end_time = time.time() + 0.2
    result = 0
    while time.time() < end_time:
        result += math.sqrt(random.random())
    
    duration = (time.time() - start) * 1000
    log_request("/api/cpu", 200, duration, extra={"cpu_iterations": round(result)})
    return jsonify({
        "replica":    REPLICA_ID,
        "duration_ms": round(duration, 2),
        "message":    "CPU load simulation complete",
    }), 200


@app.route("/api/replica-info")
def replica_info():
    """
    Returns metadata about this specific replica.
    
    Useful for verifying load balancing is working:
    Call this 10 times, you should see app-1, app-2, app-3 rotating.
    """
    start = time.time()
    response = {
        "replica":  REPLICA_ID,
        "pid":      os.getpid(),          # process ID inside container
        "hostname": os.uname().nodename,  # container hostname
    }
    log_request("/api/replica-info", 200, (time.time() - start) * 1000)
    return jsonify(response), 200


@app.route("/api/burst")
def burst():
    """
    Simulates a burst of internal work — logs multiple events in one request.
    
    This shows how a single user action can generate many log lines,
    which is common in microservices (one request fans out to many services).
    """
    start = time.time()
    events = []
    
    for i in range(5):
        # Each "sub-task" takes a random amount of time
        sub_start = time.time()
        time.sleep(random.uniform(0.01, 0.05))
        sub_duration = (time.time() - sub_start) * 1000
        
        event = {"step": i + 1, "duration_ms": round(sub_duration, 2)}
        events.append(event)
        
        # Log each sub-step individually — visible as separate lines in Grafana
        logger.info("burst step completed", extra={
            "replica":     REPLICA_ID,
            "step":        i + 1,
            "duration_ms": round(sub_duration, 2),
            "path":        "/api/burst",
        })
    
    total_duration = (time.time() - start) * 1000
    log_request("/api/burst", 200, total_duration, extra={"steps": 5})
    return jsonify({"replica": REPLICA_ID, "events": events}), 200


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Port 5000 inside the container. Nginx proxies to this port.
    # debug=False in production — debug mode leaks internals and is slow.
    logger.info("starting up", extra={"replica": REPLICA_ID, "port": 5000})
    app.run(host="0.0.0.0", port=5000, debug=False)
