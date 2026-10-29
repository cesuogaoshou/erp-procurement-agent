export type Role = "buyer" | "approver";

export interface Session {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  role: Role;
}

export interface Material {
  id: number;
  code: string;
  name: string;
  unit: string;
  safety_stock: string;
}

export interface Inventory {
  material_id: number;
  on_hand: string;
  reserved: string;
  available_supply: string;
  version: number;
}

export interface Forecast {
  material_id: number;
  horizon_days: number;
  model_name: string;
  strategy_type: string;
  selected_model_name: string;
  config_version: string;
  fallback_model_name: string;
  fallback_reason: string | null;
  training_range: Record<string, unknown>;
  forecast_range: Record<string, unknown>;
  evidence_ref: string;
  forecast_evidence: Record<string, unknown>;
  forecast_demand: string;
  safety_stock: string;
  available_supply: string;
  shortage_quantity: string;
  notes: string[];
}

export interface Recommendation {
  supplier_id: number;
  supplier_name: string;
  unit_price: string;
  total_amount: string;
  score: string;
  evidence: Record<string, unknown>;
}

export interface RecommendationResponse {
  recommendations: Recommendation[];
  excluded: Array<{ supplier_id: number; supplier_name: string; reasons: string[] }>;
}

export interface AgentRun {
  confirmation_fingerprint?: string | null;
  business_message: string;
  next_action: string;
  model_response: string;
  run_id: number | null;
  status: string;
  tool_calls: string[];
  purchase_order_id: number | null;
  total_amount: string | null;
  error: string | null;
  real_function_calling: boolean;
  langgraph_executed: boolean;
}

export interface AgentRunSummary {
  confirmation_fingerprint?: string | null;
  business_message: string;
  next_action: string;
  model_response: string;
  id: number;
  status: string;
  prompt: string;
  error: string | null;
  purchase_order_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ToolTrace {
  id: number;
  run_id: number;
  step_index: number;
  tool_name: string;
  arguments: Record<string, unknown>;
  output: Record<string, unknown> | unknown[];
  status: string;
  error: string | null;
  created_at: string;
}

export interface PurchaseOrder {
  delivery_requirement: string;
  recommendation_basis: string;
  id: number;
  supplier_id: number;
  supplier_name?: string;
  status: string;
  total_amount: string;
  total_budget: string | null;
  idempotency_key: string;
  version: number;
  formal_order_number: string | null;
  evidence_refs?: unknown;
  items: Array<{ material_id: number; material_name: string; unit: string; quantity: string; unit_price: string; line_amount: string }>;
  created_at?: string;
  updated_at?: string;
}

export interface DemandPoint {
  date: string;
  quantity: string;
}
