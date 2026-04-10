/**
 * script.js — Traffic Lab Control Panel Logic
 *
 * This file does 3 things:
 *   1. Sends HTTP requests to the Nginx/Flask backend
 *   2. Displays responses in the log table
 *   3. Runs the auto traffic generator (interval-based)
 *
 * DATA FLOW (client side):
 *   Button click → fetch(endpoint) → Nginx:8085 → Flask replica
 *   → response → update log table + counters
 *
 * The server side (Flask → Promtail → Loki → Grafana) happens
 * automatically — you just need to send requests.
 */

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────

// Counters shown in the stats bar at the top
const counters = {
  total:     0,   // all requests sent
  success:   0,   // 2xx responses
  errors:    0,   // 5xx responses
  rateLimit: 0,   // 429 responses
};

// For calculating requests-per-second
let requestTimestamps = [];   // timestamps of last N requests
let generatorInterval = null; // setInterval handle for auto generator
let logRows = [];             // array of log entries (max 50)

// ─────────────────────────────────────────────
// CORE: SEND A REQUEST
// ─────────────────────────────────────────────

/**
 * sendRequest — sends one HTTP GET to the given endpoint.
 *
 * @param {string} endpoint - e.g. "/api/data"
 * @param {string} type     - button type for visual feedback (unused currently)
 *
 * Uses the Fetch API (modern browser built-in).
 * fetch() is async — it returns a Promise.
 * We use async/await to write it like synchronous code.
 */
async function sendRequest(endpoint, type) {
  const startTime = performance.now(); // high-resolution timer (milliseconds)

  try {
    // Send the request to Nginx (same origin — no CORS needed from UI)
    // Nginx is serving this HTML file AND proxying /api/* to Flask
    const response = await fetch(endpoint, {
      method: 'GET',
      // Cache: 'no-store' prevents browser from caching API responses
      // (important for seeing real load balancing — each request must go to server)
      cache: 'no-store',
    });

    const duration = performance.now() - startTime; // how long the request took

    // Parse the JSON response body
    // response.json() is also async — it reads the response stream
    let data = {};
    try {
      data = await response.json();
    } catch {
      // Some responses might not be valid JSON (e.g., Nginx error pages)
      data = { message: 'non-JSON response' };
    }

    // Update counters based on HTTP status code
    counters.total++;
    if (response.status >= 200 && response.status < 300) {
      counters.success++;
    } else if (response.status === 429) {
      counters.rateLimit++;
    } else if (response.status >= 500) {
      counters.errors++;
    }

    // Track timestamp for req/s calculation
    requestTimestamps.push(Date.now());

    // Add to log table
    addLogRow({
      time:     new Date().toLocaleTimeString(),
      endpoint: endpoint,
      status:   response.status,
      replica:  data.replica || 'unknown',
      duration: Math.round(duration),
      response: JSON.stringify(data).substring(0, 80), // truncate long responses
    });

  } catch (err) {
    // Network error (e.g., Nginx is down, container not running)
    const duration = performance.now() - startTime;
    counters.total++;
    counters.errors++;

    addLogRow({
      time:     new Date().toLocaleTimeString(),
      endpoint: endpoint,
      status:   'ERR',
      replica:  'N/A',
      duration: Math.round(duration),
      response: err.message, // e.g., "Failed to fetch" = server is down
    });
  }

  // Update the stats bar in the header
  updateCounterDisplay();
}

// ─────────────────────────────────────────────
// LOG TABLE
// ─────────────────────────────────────────────

/**
 * addLogRow — prepends a new row to the response log table.
 * Keeps max 50 rows to avoid memory issues.
 */
function addLogRow(entry) {
  logRows.unshift(entry); // add to front (newest first)
  if (logRows.length > 50) logRows.pop(); // remove oldest

  renderLogTable();
}

/**
 * renderLogTable — re-renders the entire log table from logRows array.
 * Simple approach: clear and rebuild. Fine for 50 rows.
 */
function renderLogTable() {
  const tbody = document.getElementById('log-tbody');

  if (logRows.length === 0) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No requests yet — click a button above</td></tr>';
    return;
  }

  // Build HTML string for all rows
  // Template literals (backticks) make this readable
  tbody.innerHTML = logRows.map(row => {
    // Determine CSS class for status badge
    let statusClass = 'status-200';
    if (row.status === 429)                statusClass = 'status-429';
    else if (row.status >= 500)            statusClass = 'status-500';
    else if (row.status === 'ERR')         statusClass = 'status-err';

    // Determine CSS class for replica badge
    const replicaClass = `replica-${row.replica}`;

    return `
      <tr>
        <td>${row.time}</td>
        <td><code>${row.endpoint}</code></td>
        <td><span class="status-badge ${statusClass}">${row.status}</span></td>
        <td><span class="replica-badge ${replicaClass}">${row.replica}</span></td>
        <td>${row.duration}ms</td>
        <td style="color: var(--text-muted); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${row.response}</td>
      </tr>
    `;
  }).join('');
}

function clearLog() {
  logRows = [];
  renderLogTable();
}

// ─────────────────────────────────────────────
// STATS BAR
// ─────────────────────────────────────────────

/**
 * updateCounterDisplay — updates the numbers in the header stats bar.
 * Also calculates requests-per-second from recent timestamps.
 */
function updateCounterDisplay() {
  document.getElementById('total-count').textContent   = counters.total;
  document.getElementById('success-count').textContent = counters.success;
  document.getElementById('error-count').textContent   = counters.errors;
  document.getElementById('ratelimit-count').textContent = counters.rateLimit;

  // Calculate req/s: count requests in the last 5 seconds
  const now = Date.now();
  const fiveSecondsAgo = now - 5000;
  // Filter to only keep timestamps from last 5 seconds
  requestTimestamps = requestTimestamps.filter(t => t > fiveSecondsAgo);
  const rps = (requestTimestamps.length / 5).toFixed(1); // divide by 5 seconds
  document.getElementById('rps').textContent = rps;
}

// ─────────────────────────────────────────────
// AUTO TRAFFIC GENERATOR
// ─────────────────────────────────────────────

let currentRate = 5; // requests per second (from slider)

/**
 * updateRate — called when slider moves.
 * Updates the display label and current rate.
 */
function updateRate(value) {
  currentRate = parseInt(value);
  document.getElementById('rate-display').textContent = currentRate;

  // If generator is running, restart it with new rate
  if (generatorInterval !== null) {
    stopGenerator();
    startGenerator();
  }
}

/**
 * startGenerator — starts sending requests automatically.
 *
 * Uses setInterval to fire every (1000 / rate) milliseconds.
 * Example: 5 req/s → fire every 200ms
 *          20 req/s → fire every 50ms
 *
 * IMPORTANT: This sends requests from the BROWSER.
 * The rate limit in Nginx is per-IP, so all these requests
 * come from the same IP (your machine) → rate limit applies.
 */
function startGenerator() {
  const endpoint = document.getElementById('endpoint-select').value;
  const intervalMs = Math.floor(1000 / currentRate); // ms between requests

  // Update UI
  document.getElementById('start-btn').disabled = true;
  document.getElementById('stop-btn').disabled  = false;
  document.getElementById('generator-status').classList.remove('hidden');
  document.getElementById('status-rate').textContent     = currentRate;
  document.getElementById('status-endpoint').textContent = endpoint;

  // Start the interval
  // setInterval(fn, ms) calls fn every ms milliseconds
  generatorInterval = setInterval(() => {
    sendRequest(endpoint, 'auto');
  }, intervalMs);
}

/**
 * stopGenerator — clears the interval, stops sending requests.
 */
function stopGenerator() {
  if (generatorInterval !== null) {
    clearInterval(generatorInterval); // stop the interval
    generatorInterval = null;
  }

  // Update UI
  document.getElementById('start-btn').disabled = false;
  document.getElementById('stop-btn').disabled  = true;
  document.getElementById('generator-status').classList.add('hidden');
}

// ─────────────────────────────────────────────
// PERIODIC UPDATES
// ─────────────────────────────────────────────

// Update req/s display every second even when not sending requests
// (so it decays to 0 when you stop)
setInterval(updateCounterDisplay, 1000);
