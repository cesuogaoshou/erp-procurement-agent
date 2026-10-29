<template>
  <el-config-provider :locale="zhCn">
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
              id="procurement-request"
              placeholder="例如：请买120件标准轴承，20天内到货，总预算5000元，先生成草稿等人工审批。"
            />
            <el-input v-model="totalBudget" aria-label="确认整单预算（元）" placeholder="确认整单预算（元），如 5000.00；仅分析可留空" maxlength="16" />
            <p class="budget-help">此金额作为整单硬上限，模型不能更改；留空时仅支持分析。</p>
            <div class="actions">
              <el-button type="primary" :disabled="!canRunAgent" :loading="agentBusy" @click="runAgent">
                分析并准备采购
              </el-button>
              <el-button :loading="refreshBusy" @click="refreshAll">刷新</el-button>
            </div>
            <el-empty v-if="!latestRun && !agentBusy" description="暂无执行结果" />
            <div v-if="latestRun" class="business-result" aria-live="polite">
              <h3>{{ statusName(latestRun.status) }}</h3>
              <p>{{ latestRun.business_message || '此历史任务没有保存业务说明，请查看关联订单或重新分析。' }}</p>
              <p><strong>下一步：</strong>{{ latestRun.next_action || '请核对需求和预算后重新运行。' }}</p>
              <el-button v-if="latestRun.status === 'awaiting_confirmation'" type="primary" :disabled="!canConfirmRequest" :loading="agentBusy" @click="confirmRequest">确认本次完整需求并准备草稿</el-button>
              <p v-if="latestRun.status === 'awaiting_confirmation' && !canConfirmRequest && !agentBusy">需求或预算已修改，旧确认失效，请重新点击“分析并准备采购”。</p>
              <el-button v-if="!latestRun.purchase_order_id" @click="supplementRequest">补充或重新确认需求</el-button>
              <el-button v-else @click="activePage = 'approval'">核对订单并提交审批</el-button>
            </div>
            <div v-if="draftOrder" class="order-summary">
              <h3>建议与草稿</h3>
              <p>供应商：{{ draftOrder.supplier_name || draftOrder.supplier_id }}</p>
              <p>整单金额：{{ money(draftOrder.total_amount) }}；{{ statusName(draftOrder.status) }}</p>
              <p>整单预算：{{ draftOrder.total_budget == null ? "未知（历史订单）" : money(draftOrder.total_budget) }}</p>
              <p>交付要求：{{ draftOrder.delivery_requirement }}</p>
              <p>推荐依据：{{ draftOrder.recommendation_basis }}</p>
              <el-table :data="draftOrder.items" size="small">
                <el-table-column prop="material_name" label="物料" min-width="120" />
                <el-table-column prop="unit" label="单位" width="60" />
                <el-table-column prop="quantity" label="数量" />
                <el-table-column prop="unit_price" label="单价" />
                <el-table-column prop="line_amount" label="行金额" />
              </el-table>
            </div>
          </div>

          <div class="panel">
            <div class="panel-heading">
              <h2>排查详情</h2>
              <el-button size="small" :disabled="!latestRun?.run_id" :loading="traceBusy" @click="loadTraces">重载</el-button>
            </div>
            <details>
            <summary>展开工具调用和原始技术数据</summary>
            <p>记录编号：{{ latestRun?.run_id || '-' }}</p>
            <p v-if="latestRun?.model_response">模型辅助说明（未经业务确认）：{{ latestRun.model_response }}</p>
            <el-empty v-if="traces.length === 0 && !traceBusy" description="暂无技术记录" />
            <el-timeline v-else>
              <el-timeline-item v-for="trace in traces" :key="trace.id" :type="trace.status === 'ok' ? 'success' : 'danger'">
                <div class="trace-title">#{{ trace.step_index }} {{ trace.tool_name }}</div>
                <pre>{{ shortJson(trace.output) }}</pre>
              </el-timeline-item>
            </el-timeline>
            </details>
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
              <el-table-column label="状态" width="130"><template #default="{ row }">{{ statusName(row.status) }}</template></el-table-column>
              <el-table-column prop="version" label="版本" width="80" />
              <el-table-column prop="total_amount" label="金额" width="120" />
              <el-table-column label="整单预算" width="130">
                <template #default="{ row }">{{ row.total_budget == null ? "未知（历史）" : money(row.total_budget) }}</template>
              </el-table-column>
              <el-table-column prop="formal_order_number" label="正式单号" width="150" />
              <el-table-column label="操作" width="360">
                <template #default="{ row }">
                  <el-button size="small" @click="selectedOrder = row">查看明细</el-button>
                  <el-button size="small" :disabled="session?.role !== 'buyer' || row.status !== 'draft' || actionBusy" @click="submitOrder(row)">提交</el-button>
                  <el-button size="small" type="success" :disabled="session?.role !== 'approver' || row.status !== 'pending_approval' || actionBusy" @click="approveOrder(row)">批准</el-button>
                  <el-button size="small" type="danger" :disabled="session?.role !== 'approver' || row.status !== 'pending_approval' || actionBusy" @click="rejectOrder(row)">驳回</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-alert class="note" title="审批前请查看明细并核对数量、金额、预算和交期。订单已被他人处理时，请刷新后查看最新结果。" type="info" :closable="false" />
            <el-dialog :model-value="Boolean(selectedOrder)" title="采购订单明细" width="760px" @close="selectedOrder = null">
              <template v-if="selectedOrder">
                <p>订单{{ selectedOrder.id }} · {{ statusName(selectedOrder.status) }} · {{ selectedOrder.supplier_name }}</p>
                <p>整单金额：{{ money(selectedOrder.total_amount) }}；整单预算：{{ selectedOrder.total_budget == null ? '无法确认（历史订单）' : money(selectedOrder.total_budget) }}</p>
                <p>交付要求：{{ selectedOrder.delivery_requirement }}</p>
                <p>推荐依据：{{ selectedOrder.recommendation_basis }}</p>
                <el-table :data="selectedOrder.items">
                  <el-table-column prop="material_name" label="物料" min-width="120" />
                  <el-table-column prop="unit" label="单位" />
                  <el-table-column prop="quantity" label="数量" />
                  <el-table-column prop="unit_price" label="单价（元）" />
                  <el-table-column prop="line_amount" label="行金额（元）" />
                </el-table>
                <p>采购员核对并提交后，由审批员人工决定是否批准。</p>
              </template>
              <template #footer><el-button @click="selectedOrder = null">关闭明细</el-button></template>
            </el-dialog>
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
              <el-table-column label="状态" width="130"><template #default="{ row }">{{ statusName(row.status) }}</template></el-table-column>
              <el-table-column prop="prompt" label="需求" min-width="220" show-overflow-tooltip />
              <el-table-column prop="purchase_order_id" label="订单" width="90" />
              <el-table-column prop="business_message" label="业务结论" min-width="240" show-overflow-tooltip />
            </el-table>
          </div>
          <div class="panel">
            <div class="panel-heading">
              <h2>业务结果与关联订单</h2>
              <span class="muted">{{ selectedRunId ? `Run #${selectedRunId}` : "选择左侧任务" }}</span>
            </div>
            <el-empty v-if="!selectedRunId" description="未选择任务" />
            <template v-else>
            <p>{{ latestRun?.business_message || '历史任务未保存业务说明，请核对关联订单。' }}</p>
            <p>{{ latestRun?.next_action }}</p>
            <details><summary>展开排查详情</summary>
            <p v-if="latestRun?.model_response">模型辅助说明（未经业务确认）：{{ latestRun.model_response }}</p>
            <el-timeline>
              <el-timeline-item v-for="trace in traces" :key="trace.id" :type="trace.status === 'ok' ? 'success' : 'danger'">
                <div class="trace-title">{{ trace.tool_name }} / {{ trace.status }}</div>
                <pre>{{ shortJson(trace.error || trace.output) }}</pre>
              </el-timeline-item>
            </el-timeline>
            </details>
            </template>
          </div>
        </section>
      </main>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { ElMessage, ElMessageBox } from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
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

const agentPrompt = ref(localStorage.getItem('erp-request') || "请买120件标准轴承，20天内到货，总预算5000元，先生成草稿等人工审批。");
const totalBudget = ref(localStorage.getItem('erp-budget') || "");
const agentBusy = ref(false);
const latestRun = ref<AgentRun | null>(null);
const confirmationSource = ref({ prompt: '', budget: '' });
const canConfirmRequest = computed(() => Boolean(canRunAgent.value && latestRun.value?.confirmation_fingerprint && confirmationSource.value.prompt === agentPrompt.value.trim() && confirmationSource.value.budget === totalBudget.value.trim()));
watch([agentPrompt, totalBudget], () => {
  if (latestRun.value?.status === 'awaiting_confirmation') confirmationSource.value = { prompt: '', budget: '' };
});
const traces = ref<ToolTrace[]>([]);
const traceBusy = ref(false);
const runs = ref<AgentRunSummary[]>([]);
const orders = ref<PurchaseOrder[]>([]);
const refreshBusy = ref(false);
const actionBusy = ref(false);
const selectedRunId = ref<number | null>(null);
const selectedOrder = ref<PurchaseOrder | null>(null);

const token = computed(() => session.value?.access_token || "");
const canRunAgent = computed(() => Boolean(token.value && session.value?.role === "buyer" && agentPrompt.value.trim() && !agentBusy.value));
const pageTitle = computed(() => ({ agent: "智能采购", analysis: "数据分析", approval: "采购审批", records: "执行记录" })[activePage.value]);
const connectionText = computed(() => (session.value ? `${session.value.role === 'buyer' ? '采购员' : '审批员'}（${session.value.user_id}）` : "未登录"));
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
    latestRun.value = null;
    traces.value = [];
    selectedRunId.value = null;
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
  latestRun.value = null;
  traces.value = [];
  localStorage.setItem('erp-request', agentPrompt.value);
  localStorage.setItem('erp-budget', totalBudget.value);
  try {
    confirmationSource.value = { prompt: agentPrompt.value.trim(), budget: totalBudget.value.trim() };
    latestRun.value = await api.runAgent(agentPrompt.value.trim(), token.value, totalBudget.value.trim() || null);
    if (latestRun.value.run_id) {
      selectedRunId.value = latestRun.value.run_id;
      await loadTraces();
    }
    await Promise.all([loadOrders(), loadRuns()]);
    ElMessage.info(statusName(latestRun.value.status));
  } catch (err) {
    handleError(err);
  } finally {
    agentBusy.value = false;
  }
}

async function confirmRequest() {
  if (!canConfirmRequest.value || !latestRun.value?.run_id || !latestRun.value.confirmation_fingerprint) return;
  agentBusy.value = true;
  try {
    latestRun.value = await api.confirmRequest(latestRun.value.run_id, agentPrompt.value.trim(), totalBudget.value.trim(), latestRun.value.confirmation_fingerprint, token.value);
    selectedRunId.value = latestRun.value.run_id;
    await Promise.all([loadOrders(), loadRuns(), loadTraces()]);
    ElMessage.info(statusName(latestRun.value.status));
  } catch (err) { handleError(err); }
  finally { agentBusy.value = false; }
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
  const reason = await ElMessageBox.prompt("请输入驳回原因", "驳回采购单", { inputValue: "", confirmButtonText: "确认驳回", cancelButtonText: "取消", inputValidator: (value) => Boolean(value?.trim()) || '请填写驳回原因' })
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
    business_message: row.business_message,
    next_action: row.next_action,
    model_response: row.model_response,
    confirmation_fingerprint: row.confirmation_fingerprint,
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
  let message = '连接失败，请检查服务是否启动，稍后重试。您的需求已保留。';
  if (err instanceof ApiError) {
    if (err.status === 401 && err.message === 'invalid_credentials') {
      message = '账号或密码不正确，请核对后重试。';
    } else if (err.status === 401) {
      message = '登录已过期，请重新登录';
      localStorage.setItem('erp-request', agentPrompt.value);
      localStorage.setItem('erp-budget', totalBudget.value);
      localStorage.removeItem('erp-session');
      session.value = null;
    } else if (err.status === 403) message = '当前账号无权执行此操作，请使用订单所属采购员或审批员账号。';
    else if (err.status === 409) message = '订单可能已被处理或本次操作与原记录不一致，请刷新订单，核对最新状态后再操作。';
    else if (err.status === 422) message = '填写的信息不符合要求，请检查数量、预算、交期或审批原因后重试。';
    else message = '处理暂未完成，请稍后重试；若仍失败，请联系管理员。';
  }
  error.value = message;
  ElMessage.error(message);
}

function supplementRequest() {
  document.getElementById('procurement-request')?.focus();
  ElMessage.info('请在上方补充或修改需求及预算，再点击“分析并准备采购”。');
}

function statusName(status: string) {
  return ({ awaiting_confirmation: '请确认完整需求', confirmation_consumed: '本次确认已使用', draft_created: '草稿已生成', draft: '草稿已生成', pending_approval: '待审批', approved: '已批准', rejected: '已驳回', needs_information: '需要补充信息', material_ambiguous: '需要选择物料', material_not_found: '未找到物料', no_qualified_suppliers: '无法满足采购条件', tool_error: '未生成订单，请核对条件', completed: '分析已完成', no_shortage: '暂无采购缺口', running: '正在分析', timeout: '处理超时，请重试', provider_error: '分析服务暂不可用', failed: '处理未完成', max_tool_calls_exceeded: '处理未完成，请简化需求后重试' } as Record<string, string>)[status] || '请查看业务结果';
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
