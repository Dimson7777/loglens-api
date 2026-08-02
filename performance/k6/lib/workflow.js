import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

function jsonHeaders(token) {
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export function setupUser() {
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10000)}`;
  const email = `k6-${suffix}@example.com`;
  const password = "supersecurepass123";

  const registerRes = http.post(
    `${BASE_URL}/api/v1/auth/register`,
    JSON.stringify({ email, password }),
    { headers: jsonHeaders() }
  );

  check(registerRes, {
    "register returns 201": (r) => r.status === 201,
  });

  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email, password }),
    { headers: jsonHeaders() }
  );

  check(loginRes, {
    "login returns 200": (r) => r.status === 200,
    "login has access token": (r) => !!r.json("token.access_token"),
  });

  if (loginRes.status !== 200) {
    fail(`Unable to authenticate test user, status=${loginRes.status}`);
  }

  return {
    token: loginRes.json("token.access_token"),
  };
}

export function runWorkflow(data) {
  const token = data.token;

  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    "health returns 200": (r) => r.status === 200,
  });

  const singleLogPayload = {
    service_name: "checkout-api",
    environment: "staging",
    log_level: "error",
    message: `Checkout error ${Date.now()}`,
    exception_type: "RuntimeError",
    stack_trace: "Traceback: simulated",
    metadata: { source: "k6" },
    timestamp: new Date().toISOString(),
  };

  const ingestRes = http.post(
    `${BASE_URL}/api/v1/logs`,
    JSON.stringify(singleLogPayload),
    { headers: jsonHeaders(token) }
  );
  check(ingestRes, {
    "single ingest returns 201": (r) => r.status === 201,
  });

  const listLogsRes = http.get(`${BASE_URL}/api/v1/logs?page=1&page_size=20`, {
    headers: jsonHeaders(token),
  });
  check(listLogsRes, {
    "list logs returns 200": (r) => r.status === 200,
  });

  const groupsRes = http.get(`${BASE_URL}/api/v1/error-groups?page=1&page_size=20`, {
    headers: jsonHeaders(token),
  });
  check(groupsRes, {
    "list groups returns 200": (r) => r.status === 200,
  });

  const bulkPayload = {
    idempotency_key: `k6-bulk-${Date.now()}-${Math.floor(Math.random() * 10000)}`,
    logs: [
      {
        service_name: "checkout-api",
        environment: "staging",
        log_level: "warning",
        message: "bulk item 1",
        exception_type: null,
        stack_trace: null,
        metadata: { source: "k6" },
        timestamp: new Date().toISOString(),
      },
      {
        service_name: "checkout-api",
        environment: "staging",
        log_level: "error",
        message: "bulk item 2",
        exception_type: "ValueError",
        stack_trace: "Traceback: simulated",
        metadata: { source: "k6" },
        timestamp: new Date().toISOString(),
      },
    ],
  };

  const bulkRes = http.post(
    `${BASE_URL}/api/v1/logs/bulk`,
    JSON.stringify(bulkPayload),
    { headers: jsonHeaders(token) }
  );
  check(bulkRes, {
    "bulk ingest returns 202": (r) => r.status === 202,
    "bulk has job id": (r) => !!r.json("job_id"),
  });
}
