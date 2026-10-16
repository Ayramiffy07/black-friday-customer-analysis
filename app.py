"""Local Streamlit demo for the approved SQL metric assistant."""
import importlib.util
from pathlib import Path
import sqlite3
import altair as alt

import pandas as pd
import streamlit as st
import metric_store


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("metric_assistant", ROOT / "19_metric_assistant.py")
assistant = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assistant)

st.set_page_config(page_title="零售经营分析助手", page_icon="📊", layout="wide")
st.markdown("""
<style>
.stApp {background:#f5f7fb;color:#182338}
[data-testid="stSidebar"] {background:#edf2f8}
.block-container {padding-top:1.5rem;max-width:1380px}
h1,h2,h3 {color:#172840!important;letter-spacing:-.025em}
[data-testid="stMetric"] {background:white;border:1px solid #e4eaf2;border-radius:14px;padding:18px}
[data-testid="stMetricLabel"] {color:#65738a}
[data-testid="stMetricValue"] {color:#182d4c}
[data-testid="stForm"] {background:white;border:1px solid #e4eaf2;border-radius:16px;padding:20px}
.hero {background:linear-gradient(115deg,#152b4b,#254b75);border-radius:14px;padding:16px 24px;margin-bottom:12px;color:white}
.hero h1 {color:white!important;font-size:30px;margin:8px 0}
.hero p {color:#c9d9ec;margin:0;font-size:14px}
.badge {color:#a9d9fc;font-size:12px;letter-spacing:.15em}
</style>
<div class="hero"><div class="badge">RETAIL INSIGHT / 经营分析工作台</div>
<h1>零售经营分析工作台</h1>
<p>查询消费贡献 · 比较客群表现 · 查看指标依据 · 导出分析结果</p></div>
""", unsafe_allow_html=True)
st.caption("个人作品集 / 单用户本地原型 / 规则驱动，尚未接入大模型")

with st.sidebar:
    st.markdown("### RETAIL INSIGHT")
    st.caption("经营分析工作台 · v0.3")
    st.divider()
    st.markdown("**工作区**")
    st.write("客群贡献分析")
    with st.expander("数据状态与使用帮助"):
        st.write("来源：Kaggle Black Friday；无日期、订单编号和成本字段。")
        st.write("支持客群排名、年龄与性别筛选、指标解释和同年龄段男女对比。")
        st.write("运行模式：本地规则版。")

if not (ROOT / "data/processed/retail.sqlite").exists() and not (ROOT / "reports/sql_customer_contribution.csv").exists():
    st.warning("数据库尚未准备，请先运行 18_sql_metric_foundation.py，再刷新页面。")
    st.stop()
if metric_store.uses_demo():
    st.caption("公开演示模式：使用已核验的客群汇总快照，保留当前指标查询；不包含用户明细，不是实时业务数据。")

examples = ["哪些客群消费贡献最高？", "26–35岁女性消费贡献是多少？", "26–35岁女性占该年龄段消费额多少？", "消费贡献是什么意思？", "20–30岁女性消费贡献是多少？", "昨天哪个客群消费最高？"]
overview = assistant.answer(examples[0])
if overview["status"] == "answered":
    overview_rows = overview["evidence"]
    st.caption(f"数据集概况 · {sum(r['user_count'] for r in overview_rows):,} 名用户 · {sum(r['record_count'] for r in overview_rows):,} 条购买记录 · {len(overview_rows)} 个年龄×性别客群 · 无时间筛选")
with st.form("question_form"):
    question = st.text_input("你想了解哪个客群？", placeholder="例如：26–35岁女性占该年龄段消费额多少？")
    example = st.selectbox("示例问题（输入为空时使用）", examples)
    submitted = st.form_submit_button("查询分析", type="primary")

with st.expander("按条件查询客群 · 无需组织问题"):
    with st.form("segment_form"):
        controls = st.columns(3)
        selected_age = controls[0].selectbox("年龄段", ["0-17", "18-25", "26-35", "36-45", "46-50", "51-55", "55+"], index=2)
        selected_gender = controls[1].selectbox("性别", ["女性", "男性"])
        selected_scope = controls[2].selectbox("占比分母", ["全体用户", "该年龄段"])
        selected_submit = st.form_submit_button("分析此客群")
if selected_submit:
    question = f"{selected_age}岁{selected_gender}占{selected_scope}消费额多少？"
    submitted = True

if submitted:
    chosen = question.strip() or example
    try:
        with st.spinner("正在查询已核验的指标…"):
            response = assistant.answer(chosen)
        st.session_state["result"] = (chosen, response)
        history = st.session_state.setdefault("query_history", [])
        history.insert(0, {"问题": chosen, "状态": response["status"], "会话序号": len(history) + 1})
        del history[10:]
    except (sqlite3.Error, OSError):
        st.session_state.pop("result", None)
        st.error("查询暂时不可用，请检查本地数据库与 SQL 文件，必要时重跑数据准备脚本。")

if "result" not in st.session_state and overview["status"] == "answered":
    st.session_state["result"] = ("默认概览：哪些客群消费贡献最高？", overview)
if "result" in st.session_state:
    chosen, response = st.session_state["result"]
    st.caption(f"当前结果对应问题：{chosen}")
    if response["status"] == "answered":
        st.subheader("分析结论")
        st.info(response["answer"])
        top = response["evidence"][0]
        cards = st.columns(3)
        selected = response.get("mode") == "selected"
        cards[0].metric("查询客群用户数" if selected else "排名第一客群用户数", f"{top['user_count']:,}")
        cards[1].metric("客群累计消费额 · 原始单位", f"{top['total_purchase']:,}")
        cards[2].metric("占该年龄段消费额" if response.get("share_field") == "share_of_age_purchase" else "占全体消费额", f"{top[response.get('share_field', 'share_of_all_purchase')]:.2%}")
        evidence = pd.DataFrame(response["evidence"])
        evidence["gender"] = evidence["gender"].map({"M": "男性", "F": "女性"})
        names = {"age": "年龄段", "gender": "性别", "user_count": "用户数", "record_count": "购买记录数", "total_purchase": "累计消费额", "average_purchase": "单条平均消费额", "share_of_all_purchase": "占全体消费额", "share_of_age_purchase": "占该年龄段消费额"}
        table = evidence.rename(columns=names)
        field = names[response.get("share_field", "share_of_all_purchase")]
        columns = ["年龄段", "性别", "用户数", "累计消费额", field]
        display = table[columns].copy()
        for column in ["用户数", "累计消费额"]:
            display[column] = display[column].map(lambda value: f"{value:,.0f}")
        display[field] = display[field].map(lambda value: f"{value:.2%}")
        tabs = st.tabs(["贡献分布", "明细数据", "指标与证据"])
        with tabs[0]:
            chart_data = table.head(8).copy()
            chart_data["客群"] = chart_data["年龄段"] + "岁 · " + chart_data["性别"]
            chart_data["贡献百分比"] = chart_data[field] * 100
            chart_data["标签"] = chart_data["贡献百分比"].map(lambda v: f"{v:.2f}%")
            chart_data["重点"] = [i == 0 for i in range(len(chart_data))]
            base = alt.Chart(chart_data).encode(
                x=alt.X("贡献百分比:Q", title=f"{field}（%）", scale=alt.Scale(domain=[0, max(chart_data['贡献百分比']) * 1.16])),
                y=alt.Y("客群:N", sort="-x", title=None),
                tooltip=["客群:N", alt.Tooltip("贡献百分比:Q", format=".2f"), "用户数:Q"]
            )
            bars = base.mark_bar(cornerRadiusEnd=5).encode(color=alt.condition(alt.datum['重点'], alt.value('#387ce1'), alt.value('#a9c3e9')))
            labels = base.mark_text(align="left", dx=6, color="#273d59").encode(text="标签:N")
            chart = (bars + labels).properties(height=max(120, len(chart_data) * 32))
            st.altair_chart(chart, width="stretch")
            st.caption("排名展示前 8 名；指定客群查询仅显示该客群。消费贡献不等于利润。")
        with tabs[1]:
            st.dataframe(display, hide_index=True, width="stretch", height=360)
        with tabs[2]:
            st.write(response["scope"])
            st.write(response["source"])
            st.write("占比 = 客群累计消费额 / 对应范围消费额。购买记录数不是订单数，消费贡献不等于利润或未来价值。")
            if "parameters" in response:
                st.json(response["parameters"])
            st.code((ROOT / response["query"]).read_text(encoding="utf-8"), language="sql")
        st.download_button("下载完整结果 CSV", table.to_csv(index=False).encode("utf-8-sig"), file_name="customer_contribution.csv", mime="text/csv")
        st.caption("金额使用原始数据单位。导出占比为 0–1 小数；购买记录数不是订单数。")
        with st.expander("下一步：查看同年龄段男女对比"):
            compare_age = st.selectbox("选择对比年龄段", ["0-17", "18-25", "26-35", "36-45", "46-50", "51-55", "55+"], index=["0-17", "18-25", "26-35", "36-45", "46-50", "51-55", "55+"].index(top["age"]))
            if st.button("查看男女对比"):
                comparisons = []
                for gender in ["男性", "女性"]:
                    result = assistant.answer(f"{compare_age}岁{gender}占该年龄段消费额多少？")
                    if result["status"] == "answered":
                        row = result["evidence"][0]
                        comparisons.append({"性别": gender, "用户数": row["user_count"], "累计消费额": row["total_purchase"], "人均累计消费额": row["total_purchase"] / row["user_count"], "占该年龄段消费额": row["share_of_age_purchase"]})
                if len(comparisons) == 2:
                    comparison = pd.DataFrame(comparisons)
                    st.dataframe(comparison.style.format({"累计消费额": "{:,.0f}", "人均累计消费额": "{:,.2f}", "占该年龄段消费额": "{:.2%}"}), hide_index=True, width="stretch")
                    st.caption(f"范围：{compare_age}岁全部观测用户。人均累计消费 = 累计消费额 / 去重用户数；群体人数不同，不应仅凭总额判断人均价值。证据：selected_customer_contribution.sql，分别绑定 M、F。")
    elif response["status"] == "definition":
        st.info(response["answer"])
    else:
        st.warning(response["answer"])

with st.sidebar:
    st.divider()
    st.subheader("本次会话查询")
    for item in st.session_state.get("query_history", [])[:5]:
        st.caption(f"• {item['问题']} · {item['状态']}")
    st.caption("仅保存在当前会话，不是企业审计日志。")
