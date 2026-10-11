import type {
  AgentRun,
  AgentRunSummary,
  DemandPoint,
  Forecast,
  Inventory,
  Material,
  PurchaseOrder,
  RecommendationResponse,
  Session
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text when the server returns no JSON body.
    }
    throw new ApiError(String(detail), response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  login(username: string, password: string) {
    return request<Session>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
  },
  materials(token: string) {
    return request<Material[]>("/materials", {}, token);
  },
  inventory(materialId: number, token: string) {
    return request<Inventory>(`/inventory/${materialId}`, {}, token);
  },
  demandHistory(materialId: number, token: string, days = 120) {
    return request<DemandPoint[]>(`/demand-history/${materialId}?days=${days}`, {}, token);
  },
  forecast(materialId: number, horizonDays: number, token: string) {
    return request<Forecast>(
      "/forecasts",
      { method: "POST", body: JSON.stringify({ material_id: materialId, horizon_days: horizonDays }) },
      token
    );
  },
  recommendations(materialId: number, quantity: string, requiredInDays: number, budget: string | null, token: string) {
    return request<RecommendationResponse>(
      "/recommendations",
      {
        method: "POST",
        body: JSON.stringify({
          material_id: materialId,
          quantity,
          required_in_days: requiredInDays,
          budget: budget || null
        })
      },
      token
    );
  },
  runAgent(prompt: string, token: string) {
    return request<AgentRun>(
      "/agent/runs",
      { method: "POST", body: JSON.stringify({ prompt, use_langgraph: true }) },
      token
    );
  },
  agentRuns(token: string) {
    return request<AgentRunSummary[]>("/agent/runs", {}, token);
  },
  traces(runId: number, token: string) {
    return request<import("./types").ToolTrace[]>(`/agent/runs/${runId}/traces`, {}, token);
  },
  orders(token: string) {
    return request<PurchaseOrder[]>("/purchase-orders", {}, token);
  },
  submit(orderId: number, token: string) {
    return request<PurchaseOrder>(`/purchase-orders/${orderId}/submit`, { method: "POST" }, token);
  },
  approve(orderId: number, version: number, token: string) {
    return request<PurchaseOrder>(
      `/purchase-orders/${orderId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_order_version: version,
          idempotency_key: `frontend-approve-${orderId}-${Date.now()}`
        })
      },
      token
    );
  },
  reject(orderId: number, version: number, reason: string, token: string) {
    return request<PurchaseOrder>(
      `/purchase-orders/${orderId}/reject`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_order_version: version,
          idempotency_key: `frontend-reject-${orderId}-${Date.now()}`,
          reason
        })
      },
      token
    );
  }
};
