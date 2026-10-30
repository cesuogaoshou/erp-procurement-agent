"""Generate report charts from current evaluation evidence."""
from pathlib import Path
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/generated/report_charts"
OUT.mkdir(parents=True, exist_ok=True)


def load(name):
    return json.loads((ROOT / "reports/generated" / name).read_text(encoding="utf-8"))


def style():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 160


def forecast_chart():
    data = load("forecast_comparison.json")["models"]
    labels = ["移动平均", "长历史\nProphet", "动态\nProphet", "混合策略"]
    keys = [
        "moving_average_30d",
        "prophet",
        "prophet_dynamic_seasonality",
        "hybrid_dynamic_prophet_or_moving_average_30d",
    ]
    demand = [float(data[key]["demand_metrics"]["mape_percent"]) for key in keys]
    shortage = [float(data[key]["shortage_metrics"]["mape_percent"]) for key in keys]
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bars1 = ax.bar(x - width / 2, demand, width, label="需求 MAPE", color="#4c78a8")
    bars2 = ax.bar(x + width / 2, shortage, width, label="缺口 MAPE", color="#f58518")
    for bars in (bars1, bars2):
        for bar in bars:
            ax.annotate(f"{bar.get_height():.2f}%", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8)
    ax.set_ylim(0, 9)
    ax.set_ylabel("MAPE（%）")
    ax.set_title("预测模型滚动回测 MAPE（30 天窗口，160 个窗口）")
    ax.set_xticks(x, labels)
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "forecast_mape.png")
    plt.close(fig)


def supplier_chart():
    data = load("supplier_eval.json")
    labels = ["冻结集（60 例）", "挑战集（60 例）"]
    composite = [float(data["frozen"]["composite_top3_hit_rate_percent"]), float(data["challenge"]["composite_top3_hit_rate_percent"])]
    price = [float(data["frozen"]["price_sort_top3_hit_rate_percent"]), float(data["challenge"]["price_sort_top3_hit_rate_percent"])]
    x = np.arange(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars1 = ax.bar(x - width / 2, composite, width, label="综合评分 Top-3", color="#2f9e44")
    bars2 = ax.bar(x + width / 2, price, width, label="价格排序 Top-3", color="#868e96")
    for bars in (bars1, bars2):
        for bar in bars:
            ax.annotate(f"{bar.get_height():.2f}%", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_ylabel("命中率（%）")
    ax.set_title("供应商推荐 Top-3 命中率对比")
    ax.set_xticks(x, labels)
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "supplier_hit.png")
    plt.close(fig)


def agent_chart():
    data = load("agent_input_eval.json")["summary"]
    categories = ["normal", "missing", "validation", "intent", "language", "security"]
    names = ["正常采购", "信息缺失", "条件校验", "意图判断", "语言/单位", "安全越权"]
    totals = [data["by_category"][key]["total"] for key in categories]
    passed = [data["by_category"][key]["passed"] for key in categories]
    x = np.arange(len(names))
    width = 0.5
    fig, ax = plt.subplots(figsize=(9, 4.3))
    ax.bar(x, totals, width, label="用例数", color="#d0d7de")
    ax.bar(x, passed, width, label="通过数", color="#2f9e44")
    for i, (total, good) in enumerate(zip(totals, passed)):
        ax.annotate(f"{good}/{total}", (i, total), textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8)
    ax.set_ylim(0, max(totals) + 1)
    ax.set_ylabel("用例数")
    ax.set_title(f"Agent 输入评测分类通过情况（总计 {data['passed']}/{data['case_count']}）")
    ax.set_xticks(x, names)
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "agent_eval.png")
    plt.close(fig)


if __name__ == "__main__":
    style()
    forecast_chart()
    supplier_chart()
    agent_chart()
    print("charts written to", OUT)
