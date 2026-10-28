<template>
  <el-config-provider>
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">采</div>
          <div>
            <h1>ERP智能采购Agent</h1>
            <p>最小演示工作台</p>
          </div>
        </div>
        <el-menu :default-active="activePage" class="nav" @select="activePage = $event">
          <el-menu-item index="agent">智能采购</el-menu-item>
          <el-menu-item index="analysis">数据分析</el-menu-item>
          <el-menu-item index="approval">采购审批</el-menu-item>
          <el-menu-item index="records">执行记录</el-menu-item>
        </el-menu>
      </aside>

      <main class="workspace">
        <section class="topbar">
          <div>
            <strong>{{ pageTitle }}</strong>
            <span>{{ connectionText }}</span>
          </div>
          <div class="login-panel">
            <el-select v-model="loginRole" class="role-select" size="small">
              <el-option label="采购员" value="buyer" />
              <el-option label="审批员" value="approver" />
            </el-select>
            <el-input v-model="loginPassword" class="password-input" size="small" type="password" show-password />
            <el-button size="small" type="primary" :loading="loginBusy" @click="login">登录</el-button>
          </div>
        </section>

        <el-alert v-if="error" class="page-alert" :title="error" type="error" show-icon @close="error = ''" />

        <section v-if="activePage === 'agent'" class="page-grid two-columns">
          <div class="panel">
            <div class="panel-heading">
              <h2>智能采购</h2>
              <el-tag :type="session?.role === 'buyer' ? 'success' : 'info'">采购员执行</el-tag>
            </div>
            <el-input
              v-model="agentPrompt"
              type="textarea"
              :rows="5"
              maxlength="500"
              show-word-limit
              placeholder="例如：请根据 MAT-001 的库存和未来30天需求生成采购草稿"
            />
            <div class="actions">
              <el-button type="primary" :disabled="!canRunAgent" :loading="agentBusy" @click="runAgent">
                运行真实Agent
              </el-button>
              <el-button :loading="refreshBusy" @click="refreshAll">刷新</el-button>
            </div>
            <el-empty v-if="!latestRun && !agentBusy" description="暂无执行结果" />
            <div v-if="latestRun" class="status-strip">
              <span>状态：{{ latestRun.status }}</span>
              <span>Run #{{ latestRun.run_id }}</span>
              <span>订单 #{{ latestRun.purchase_order_id || "-" }}</span>
            </div>
            <div v-if="draftOrder" class="order-summary">
              <h3>建议与草稿</h3>
              <p>供应商：{{ draftOrder.supplier_name || draftOrder.supplier_id }}</p>
              <p>金额：{{ money(draftOrder.total_amount) }}，版本：{{ draftOrder.version }}</p>
              <el-table :data="draftOrder.items" size="small">
                <el-table-column prop="material_id" label="物料" width="90" />
                <el-table-column prop="quantity" label="数量" />
                <el-table-column prop="unit_price" label="单价" />
                <el-table-column prop="line_amount" label="行金额" />
              </el-table>
            </div>
          </div>

          <div class="panel">
            <div class="panel-heading">
              <h2>工具Trace</h2>
              <el-button size="small" :disabled="!latestRun?.run_id" :loading="traceBusy" @click="loadTraces">重载</el-button>
            </div>
            <el-empty v-if="traces.length === 0 && !traceBusy" description="暂无Trace" />
            <el-timeline v-else>
              <el-timeline-item v-for="trace in traces" :key="trace.id" :type="trace.status === 'ok' ? 'success' : 'danger'">
                <div class="trace-title">#{{ trace.step_index }} {{ trace.tool_name }}</div>
                <pre>{{ shortJson(trace.output) }}</pre>
              </el-timeline-item>
            </el-timeline>
          </div>
        </section>

        <section v-if="activePage === 'analysis'" class="page-grid two-columns">
          <div class="panel">
            <div class="panel-heading">
              <h2>库存与预测</h2>
              <el-button size="small" :loading="analysisBusy" @click="loadAnalysis">分析</el-button>
            </div>
            <div class="form-row">
              <el-select v-model="selectedMaterialId" filterable placeholder="选择物料">
                <el-option v-for="material in materials" :key="material.id" :label="`${material.code} ${material.name}`" :value="material.id" />
              </el-select>
              <el-input-number v-model="horizonDays" :min="1" :max="180" />
            </div>
            <div ref="chartEl" class="chart"></div>
            <el-descriptions v-if="inventory && forecast" :column="2" size="small" border>
              <el-descriptions-item label="可用库存">{{ inventory.available_supply }}</el-descriptions-item>
              <el-descriptions-item label="安全库存">{{ forecast.safety_stock }}</el-descriptions-item>
              <el-descriptions-item label="预测需求">{{ forecast.forecast_demand }}</el-descriptions-item>
              <el-descriptions-item label="缺口">{{ forecast.shortage_quantity }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <div class="panel">
            <div class="panel-heading">
              <h2>模型与供应商评分</h2>
              <el-tag v-if="forecast" :type="forecast.fallback_reason ? 'warning' : 'success'">
                {{ forecast.selected_model_name }}
              </el-tag>
            </div>
            <el-empty v-if="!forecast" description="请选择物料并分析" />
            <template v-else>
              <p class="muted">配置：{{ forecast.config_version }}</p>
              <p class="muted">降级：{{ forecast.fallback_reason || "未降级" }}</p>
              <el-alert v-for="note in forecast.notes" :key="note" class="note" :title="note" type="info" :closable="false" />
              <el-table :data="recommendations" size="small" empty-text="暂无合格供应商">
                <el-table-column prop="supplier_name" label="供应商" min-width="120" />
                <el-table-column prop="score" label="评分" width="90" />
                <el-table-column prop="unit_price" label="单价" width="90" />
                <el-table-column label="依据" min-width="180">
                  <template #default="{ row }">{{ scoreBasis(row.evidence) }}</template>
                </el-table-column>
              </el-table>
            </template>
          </div>
        </section>

        <section v-if="activePage === 'approval'" class="page-grid">
          <div class="panel">
            <div class="panel-heading">
              <h2>采购审批</h2>
              <el-button size="small" :loading="refreshBusy" @click="loadOrders">刷新订单</el-button>
            </div>
            <el-empty v-if="orders.length === 0 && !refreshBusy" description="暂无订单" />
            <el-table v-else :data="orders" row-key="id">
              <el-table-column prop="id" label="订单" width="80" />
              <el-table-column prop="supplier_name" label="供应商" min-width="140" />
              <el-table-column prop="status" label="状态" width="130" />
              <el-table-column prop="version" label="版本" width="80" />
              <el-table-column prop="total_amount" label="金额" width="120" />
              <el-table-column prop="formal_order_number" label="正式单号" width="150" />
              <el-table-column label="操作" width="280">
                <template #default="{ row }">
                  <el-button size="small" :disabled="row.status !== 'draft' || actionBusy" @click="submitOrder(row)">提交</el-button>
                  <el-button size="small" type="success" :disabled="row.status !== 'pending_approval' || actionBusy" @click="approveOrder(row)">批准</el-button>
                  <el-button size="small" type="danger" :disabled="row.status !== 'pending_approval' || actionBusy" @click="rejectOrder(row)">驳回</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-alert class="note" title="如果订单版本已被其他操作更新，后端会返回409冲突提示，前端不会覆盖提交。" type="warning" :closable="false" />
          </div>
        </section>

        <section v-if="activePage === 'records'" class="page-grid two-columns">
          <div class="panel">
            <div class="panel-heading">
              <h2>历史任务</h2>
              <el-button size="small" :loading="refreshBusy" @click="loadRuns">刷新</el-button>
            </div>
            <el-table :data="runs" empty-text="暂无历史任务" @row-click="selectRun">
              <el-table-column prop="id" label="Run" width="80" />
              <el-table-column prop="status" label="状态" width="130" />
              <el-table-column prop="prompt" label="需求" min-width="220" show-overflow-tooltip />
              <el-table-column prop="purchase_order_id" label="订单" width="90" />
              <el-table-column prop="error" label="错误" min-width="160" show-overflow-tooltip />
            </el-table>
          </div>
          <div class="panel">
            <div class="panel-heading">
              <h2>工具结果与关联订单</h2>
              <span class="muted">{{ selectedRunId ? `Run #${selectedRunId}` : "选择左侧任务" }}</span>
            </div>
            <el-empty v-if="!selectedRunId" description="未选择任务" />
            <el-timeline v-else>
              <el-timeline-item v-for="trace in traces" :key="trace.id" :type="trace.status === 'ok' ? 'success' : 'danger'">
                <div class="trace-title">{{ trace.tool_name }} / {{ trace.status }}</div>
                <pre>{{ shortJson(trace.error || trace.output) }}</pre>
              </el-timeline-item>
            </el-timeline>
          </div>
        </section>
      </main>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import * as echarts from "echarts";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, ApiError } from "./api";
import type { AgentRun, AgentRunSummary, DemandPoint, Forecast, Inventory, Material, PurchaseOrder, Recommendation, Role, Session, ToolTrace } from "./types";

const activePage = ref("agent");
const session = ref<Session | null>(loadSession());
const loginRole = ref<Role>("buyer");
const loginPassword = ref("buyer-pass");
const loginBusy = ref(false);
const error = ref("");

const materials = ref<Material[]>([]);
const selectedMaterialId = ref<number>();
const horizonDays = ref(30);
const inventory = ref<Inventory | null>(null);
const forecast = ref<Forecast | null>(null);
const demandHistory = ref<DemandPoint[]>([]);
const recommendations = ref<Recommendation[]>([]);
const analysisBusy = ref(false);
const chartEl = ref<HTMLDivElement | null>(null);

const agentPrompt = ref("请根据 MAT-001 的库存和未来30天需求生成采购草稿");
const agentBusy = ref(false);
const latestRun = ref<AgentRun | null>(null);
const traces = ref<ToolTrace[]>([]);
const traceBusy = ref(false);
const runs = ref<AgentRunSummary[]>([]);
const orders = ref<PurchaseOrder[]>([]);
const refreshBusy = ref(false);
const actionBusy = ref(false);
const selectedRunId = ref<number | null>(null);

const token = computed(() => session.value?.access_token || "");
const canRunAgent = computed(() => Boolean(token.value && session.value?.role === "buyer" && agentPrompt.value.trim() && !agentBusy.value));
const pageTitle = computed(() => ({ agent: "智能采购", analysis: "数据分析", approval: "采购审批", records: "执行记录" })[activePage.value]);
const connectionText = computed(() => (session.value ? `${session.value.user_id} / ${session.value.role}` : "未登录"));
const draftOrder = computed(() => orders.value.find((order) => order.id === latestRun.value?.purchase_order_id));

onMounted(async () => {
  if (session.value) {
    await refreshAll();
  }
});

async function login() {
  loginBusy.value = true;
  error.value = "";
  try {
    const password = loginPassword.value || (loginRole.value === "buyer" ? "buyer-pass" : "approver-pass");
    session.value = await api.login(loginRole.value, password);
    localStorage.setItem("erp-session", JSON.stringify(session.value));
    ElMessage.success("登录成功");
    await refreshAll();
  } catch (err) {
    handleError(err);
  } finally {
    loginBusy.value = false;
  }
}

async function runAgent() {
  if (!token.value || agentBusy.value) return;
  agentBusy.value = true;
  error.value = "";
  try {
    latestRun.value = await api.runAgent(agentPrompt.value.trim(), token.value);
    if (latestRun.value.run_id) {
      selectedRunId.value = latestRun.value.run_id;
      await loadTraces();
    }
    await Promise.all([loadOrders(), loadRuns()]);
    ElMessage.success("Agent执行完成");
  } catch (err) {
    handleError(err);
  } finally {
    agentBusy.value = false;
  }
}

async function loadAnalysis() {
  if (!token.value || !selectedMaterialId.value || analysisBusy.value) return;
  analysisBusy.value = true;
  error.value = "";
  try {
    const materialId = selectedMaterialId.value;
    const [nextInventory, nextForecast, history] = await Promise.all([
      api.inventory(materialId, token.value),
      api.forecast(materialId, horizonDays.value, token.value),
      api.demandHistory(materialId, token.value, 120)
    ]);
    inventory.value = nextInventory;
    forecast.value = nextForecast;
    demandHistory.value = history;
    const quantity = Number(nextForecast.shortage_quantity) > 0 ? nextForecast.shortage_quantity : "1";
    const recs = await api.recommendations(materialId, quantity, 20, null, token.value);
    recommendations.value = recs.recommendations;
    await nextTick();
    renderChart();
  } catch (err) {
    handleError(err);
  } finally {
    analysisBusy.value = false;
  }
}

async function refreshAll() {
  if (!token.value || refreshBusy.value) return;
  refreshBusy.value = true;
  try {
    await Promise.all([loadMaterials(), loadOrders(), loadRuns()]);
  } catch (err) {
    handleError(err);
  } finally {
    refreshBusy.value = false;
  }
}

async function loadMaterials() {
  materials.value = await api.materials(token.value);
  selectedMaterialId.value ||= materials.value[0]?.id;
}

async function loadOrders() {
  orders.value = await api.orders(token.value);
}

async function loadRuns() {
  runs.value = await api.agentRuns(token.value);
}

async function loadTraces() {
  const runId = selectedRunId.value || latestRun.value?.run_id;
  if (!token.value || !runId) return;
  traceBusy.value = true;
  try {
    traces.value = await api.traces(runId, token.value);
  } catch (err) {
    handleError(err);
  } finally {
    traceBusy.value = false;
  }
}

async function submitOrder(order: PurchaseOrder) {
  if (!token.value || actionBusy.value) return;
  actionBusy.value = true;
  try {
    await api.submit(order.id, token.value);
    await loadOrders();
    ElMessage.success("已提交审批");
  } catch (err) {
    handleError(err);
  } finally {
    actionBusy.value = false;
  }
}

async function approveOrder(order: PurchaseOrder) {
  if (!token.value || actionBusy.value) return;
  actionBusy.value = true;
  try {
    await api.approve(order.id, order.version, token.value);
    await loadOrders();
    ElMessage.success("已批准并生成正式订单");
  } catch (err) {
    handleError(err);
  } finally {
    actionBusy.value = false;
  }
}

async function rejectOrder(order: PurchaseOrder) {
  if (!token.value || actionBusy.value) return;
  const reason = await ElMessageBox.prompt("请输入驳回原因", "驳回采购单", { inputValue: "审批驳回" })
    .then((result) => result.value)
    .catch(() => "");
  if (!reason) return;
  actionBusy.value = true;
  try {
    await api.reject(order.id, order.version, reason, token.value);
    await loadOrders();
    ElMessage.success("已驳回");
  } catch (err) {
    handleError(err);
  } finally {
    actionBusy.value = false;
  }
}

async function selectRun(row: AgentRunSummary) {
  selectedRunId.value = row.id;
  latestRun.value = {
    run_id: row.id,
    status: row.status,
    tool_calls: [],
    purchase_order_id: row.purchase_order_id,
    total_amount: null,
    error: row.error,
    real_function_calling: false,
    langgraph_executed: false
  };
  await loadTraces();
}

function renderChart() {
  if (!chartEl.value || !forecast.value) return;
  const chart = echarts.init(chartEl.value);
  const historyValues = demandHistory.value.map((point) => Number(point.quantity));
  const labels = demandHistory.value.map((point) => point.date.slice(5));
  labels.push(`预测${forecast.value.horizon_days}天`);
  chart.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 42, right: 20, top: 24, bottom: 36 },
    xAxis: { type: "category", data: labels },
    yAxis: { type: "value" },
    series: [
      { name: "历史日需求", type: "line", smooth: true, data: [...historyValues, null], showSymbol: false },
      { name: "累计预测需求", type: "bar", data: [...new Array(historyValues.length).fill(null), Number(forecast.value.forecast_demand)] },
      { name: "预测缺口", type: "bar", data: [...new Array(historyValues.length).fill(null), Number(forecast.value.shortage_quantity)] }
    ]
  });
}

function scoreBasis(evidence: Record<string, unknown>) {
  const components = evidence.score_components as Record<string, unknown> | undefined;
  if (!components) return "后端综合评分";
  return Object.entries(components)
    .slice(0, 4)
    .map(([key, value]) => `${key}:${value}`)
    .join(" / ");
}

function money(value: string) {
  return `￥${Number(value).toFixed(2)}`;
}

function shortJson(value: unknown) {
  const text = JSON.stringify(value, null, 2);
  return text.length > 900 ? `${text.slice(0, 900)}\n...` : text;
}

function handleError(err: unknown) {
  const message = err instanceof ApiError ? `${err.status}: ${err.message}` : err instanceof Error ? err.message : String(err);
  error.value = message;
  ElMessage.error(message);
}

function loadSession() {
  const raw = localStorage.getItem("erp-session");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    localStorage.removeItem("erp-session");
    return null;
  }
}
</script>
