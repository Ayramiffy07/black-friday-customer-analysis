"""Local Streamlit demo for the approved SQL metric assistant."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import os
import time
import altair as alt

import pandas as pd
import streamlit as st
import metric_store
import controlled_query
import controlled_rag
import rag_retriever
from customer_analysis import build_analysis, build_brief
from query_presentation import condition_rows, query_receipt


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
[data-testid="stMetricValue"] {color:#182d4c;font-size:clamp(1.25rem,2.3vw,2rem)}
[data-testid="stMetricLabel"] p {white-space:normal}
.stButton button[kind="primary"] {border-radius:9px;padding:.45rem 1.4rem}
@media(max-width:800px) {.block-container {padding:1rem}.hero {padding:14px}.hero h1 {font-size:23px}}
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
model_enabled = os.environ.get("RETAIL_ENABLE_MODEL") == "1"
st.caption("个人作品集 / 单用户原型 / 默认规则查询" + (" / 已启用本地受控模型试用" if model_enabled else " / 公开模式未开放模型调用"))

def render_customer_analysis(overview):
    st.divider()
    st.subheader("客群机会分析 · 多指标比较")
    st.caption("独立分析区：固定使用全体14个客群，不随上方单客群查询变化。用于提出运营假设，不自动分配营销预算。")
    analysis, baseline = build_analysis(overview["evidence"])
    options = {"消费贡献": "share_of_all_purchase", "人均累计消费": "spend_per_user", "用户规模": "user_count", "人均购买记录数": "records_per_user"}
    sort_label = st.selectbox("比较目标", list(options), key="analysis_sort")
    ordered = analysis.sort_values([options[sort_label], "age", "gender"], ascending=[False, True, True])
    leader = ordered.iloc[0]
    st.write(f"按{sort_label}排序，首位客群：**{leader['segment']}**。不同排序目标可能得到不同结论。")
    st.caption("阅读顺序：先选比较目标，再结合用户规模核查结果，最后下载简报。人均消费是历史累计值，不是未来客户价值。")
    cols = ["segment", "user_count", "total_purchase", "share_of_all_purchase", "spend_per_user", "records_per_user", "spend_vs_baseline"]
    labels = {"segment": "客群", "user_count": "用户数", "total_purchase": "累计消费额", "share_of_all_purchase": "占全体消费额", "spend_per_user": "人均累计消费", "records_per_user": "人均购买记录数", "spend_vs_baseline": "人均消费/全体均值"}
    comparison_table = ordered[cols].rename(columns=labels)
    chart_data = ordered.head(6).copy()
    chart_data["比较值"] = chart_data[options[sort_label]] * (100 if sort_label == "消费贡献" else 1)
    unit = "（%）" if sort_label == "消费贡献" else "（原始金额单位）" if sort_label == "人均累计消费" else ""
    comparison_chart = alt.Chart(chart_data).mark_bar(color="#387ce1", cornerRadiusEnd=4).encode(
        x=alt.X("比较值:Q", title=sort_label + unit),
        y=alt.Y("segment:N", sort="-x", title=None),
        tooltip=[alt.Tooltip("segment:N", title="客群"), alt.Tooltip("比较值:Q", title=sort_label, format=",.2f"), alt.Tooltip("user_count:Q", title="用户数")],
    ).properties(height=210)
    st.altair_chart(comparison_chart, width="stretch")
    st.caption("图表展示当前指标前6名；下表和导出保留全部14个客群。")
    st.dataframe(comparison_table.style.format({"用户数": "{:,.0f}", "累计消费额": "{:,.0f}", "占全体消费额": "{:.2%}", "人均累计消费": "{:,.2f}", "人均购买记录数": "{:.2f}", "人均消费/全体均值": "{:.2f}"}), hide_index=True, width="stretch", height=320)
    brief = build_brief(analysis, baseline, overview["source"])
    with st.expander("查看分析简报与建议边界"):
        st.markdown(brief)
    exports = st.columns(2)
    exports[0].download_button("下载客群分析简报", brief.encode("utf-8-sig"), file_name="customer_analysis_brief.md", mime="text/markdown")
    exports[1].download_button("下载多指标比较表", comparison_table.to_csv(index=False).encode("utf-8-sig"), file_name="customer_comparison.csv", mime="text/csv")

with st.sidebar:
    st.markdown("### RETAIL INSIGHT")
    st.caption("经营分析工作台 · v0.6 · RAG 本地验证版")
    st.divider()
    st.markdown("**工作区**")
    st.write("客群贡献分析")
    query_mode = "rule"
    if model_enabled:
        chosen_mode = st.radio("问题理解方式", ["规则模式", "模型试用"], key="query_mode")
        query_mode = "model" if chosen_mode == "模型试用" else "rule"
        count = st.session_state.get("model_attempts", 0)
        st.caption(f"本会话模型提交次数：{count}/5。此限制不是全局费用上限。")
        if not os.environ.get("DEEPSEEK_API_KEY"):
            st.warning("启动进程未配置密钥，模型查询将不可用。规则模式可正常使用。")
    with st.expander("数据状态与使用帮助"):
        st.write("来源：Kaggle Black Friday；无日期、订单编号和成本字段。")
        st.write("支持客群排名、年龄与性别筛选、指标解释和同年龄段男女对比。")
        st.write("数值问题由受控参数与 SQL 处理；指标定义、数据边界和产品说明由 RAG 知识库回答并展示引用。")
        st.write("条件筛选、默认概览、多指标分析与公开版知识检索不调用模型。")
        st.caption("模型模式会将本次问题发送到 DeepSeek；不发送购买明细。请勿输入个人或客户敏感信息。")

if not (ROOT / "data/processed/retail.sqlite").exists() and not (ROOT / "reports/sql_customer_contribution.csv").exists():
    st.warning("数据库尚未准备，请先运行 18_sql_metric_foundation.py，再刷新页面。")
    st.stop()
if metric_store.uses_demo():
    st.caption("公开演示模式：使用已核验的客群汇总快照，保留当前指标查询；不包含用户明细，不是实时业务数据。")

examples = ["哪些客群消费贡献最高？", "26–35岁女性消费贡献是多少？", "26–35岁女性占该年龄段消费额多少？", "18至25岁的姑娘在全部消费里占多少？", "消费贡献是什么意思？", "20–30岁女性消费贡献是多少？", "昨天哪个客群消费最高？"]
overview = assistant.answer(examples[0])
if overview["status"] == "answered":
    overview_rows = overview["evidence"]
    st.caption(f"数据集概况 · {sum(r['user_count'] for r in overview_rows):,} 名用户 · {sum(r['record_count'] for r in overview_rows):,} 条购买记录 · {len(overview_rows)} 个年龄×性别客群 · 无时间筛选")
with st.expander("第一次使用？按一个业务任务体验"):
    st.write("① 查贡献：找出贡献最高的客群。② 换口径：查询某客群占全体或同龄人消费的比例。③ 做判断：在下方多指标分析比较人数与人均消费，再导出简报。")
    st.caption("自然语言入口只支持白名单内的贡献查询。多指标比较使用固定程序；当前没有日期、门店、库存或订单数据，不能回答真实门店销量与复购问题。")
with st.form("question_form"):
    question = st.text_input("你想了解哪个客群？", placeholder="例如：26–35岁女性占该年龄段消费额多少？", max_chars=500)
    example = st.selectbox("示例问题（输入为空时使用）", examples)
    submitted = st.form_submit_button("查询分析", type="primary")

with st.expander("按条件查询客群 · 无需组织问题"):
    with st.form("segment_form"):
        controls = st.columns(3)
        selected_age = controls[0].selectbox("年龄段", ["0-17", "18-25", "26-35", "36-45", "46-50", "51-55", "55+"], index=2)
        selected_gender = controls[1].selectbox("性别", ["女性", "男性"])
        selected_scope = controls[2].selectbox("占比分母", ["全体用户", "该年龄段"])
        selected_submit = st.form_submit_button("分析此客群")

st.divider()
st.subheader("指标知识问答 · RAG")
st.caption("用于查询指标定义、数据限制、产品能力和评测口径。经营数值仍由上方 SQL 路径计算。回答会展示知识库文档与章节。")
rag_examples = [
    "购买记录数是不是订单数？",
    "人均累计消费是怎么计算的？",
    "为什么不能查看本月同比？",
    "评测20/20是不是说明生产准确率100%？",
    "消费金额是什么币种？",
]
with st.form("knowledge_form"):
    rag_question = st.text_input("你想了解哪个口径或限制？", placeholder="例如：购买记录数是不是订单数？", max_chars=500)
    rag_example = st.selectbox("知识问答示例（输入为空时使用）", rag_examples)
    rag_submitted = st.form_submit_button("检索知识并回答", type="primary")

if rag_submitted:
    chosen_rag_question = rag_question.strip() or rag_example
    rag_started = time.perf_counter()
    if model_enabled:
        count = st.session_state.get("model_attempts", 0)
        if count >= 5:
            rag_response = {
                "status": "model_error",
                "answer": "本会话已达5次模型提交上限。此限制不是跨会话的费用保护。",
                "error_code": "session_limit",
                "citations": [],
                "model_called": False,
            }
        elif not os.environ.get("DEEPSEEK_API_KEY"):
            rag_response = {
                "status": "model_error",
                "answer": "启动进程未配置密钥，本次未调用模型。",
                "error_code": "missing_api_key",
                "citations": [],
                "model_called": False,
            }
        else:
            st.session_state["model_attempts"] = count + 1
            with st.spinner("正在检索批准知识并生成引用回答…"):
                rag_response = controlled_rag.answer(chosen_rag_question)
            rag_response["ui_mode"] = "grounded_model"
    else:
        rag_response = rag_retriever.retrieval_response(chosen_rag_question)
        rag_response["ui_mode"] = "retrieval_only"
    rag_response["ui_elapsed_ms"] = round((time.perf_counter() - rag_started) * 1000, 2)
    st.session_state["rag_result"] = (chosen_rag_question, rag_response)

if "rag_result" in st.session_state:
    chosen_rag_question, rag_response = st.session_state["rag_result"]
    st.caption(f"当前知识问题：{chosen_rag_question}")
    if rag_response["status"] == "answered":
        st.success(rag_response["answer"])
        st.caption("回答路径：批准知识检索 → DeepSeek 受控生成 → 引用 ID 校验。")
        st.caption("模型生成内容请结合下方引用原文核查；经营数值仍以上方 SQL 查询为准。")
    elif rag_response["status"] == "retrieved":
        st.info("公开模式仅展示免费检索依据；本次没有调用模型生成答案。")
    elif rag_response["status"] == "unsupported":
        st.warning(rag_response["answer"] if "answer" in rag_response else rag_response["message"])
    else:
        st.error(rag_response.get("answer", "知识问答暂时不可用。"))
        if rag_response.get("error_code"):
            st.code(rag_response["error_code"], language="text")

    rag_citations = rag_response.get("citations", [])
    if rag_citations:
        citation_rows = [
            {
                "文档ID": item.get("doc_id", ""),
                "文档": item.get("document_title", ""),
                "章节": item.get("section", ""),
                "版本": item.get("version", ""),
                "排序分数（非概率）": round(item.get("retrieval_score", item.get("score", 0)), 3),
                "来源": item.get("source", ""),
            }
            for item in rag_citations
        ]
        st.dataframe(pd.DataFrame(citation_rows), hide_index=True, width="stretch")
        st.caption("排序分数只用于同一次问题中的章节排序，不是准确率或置信概率，也不适合跨问题比较。")
        with st.expander("查看引用原文"):
            for item in rag_citations:
                st.markdown(f"**{item.get('citation', item.get('doc_id', '知识来源'))}**")
                st.write(item.get("text", ""))

    rag_telemetry = rag_response.get("telemetry", {})
    if rag_telemetry:
        with st.expander("查看 RAG 版本、耗时与用量"):
            st.write(f"提示词版本：{rag_telemetry.get('prompt_version', '未记录')}")
            st.write(f"接口耗时：{rag_telemetry.get('latency_ms', 0) / 1000:.2f} 秒")
            if rag_telemetry.get("usage"):
                st.json(rag_telemetry["usage"])
    safe_rag_export = {
        "question": chosen_rag_question,
        "status": rag_response.get("status"),
        "answer": rag_response.get("answer", rag_response.get("message", "")),
        "citations": rag_citations,
        "decision_source": rag_response.get("decision_source"),
        "telemetry": rag_telemetry,
    }
    st.download_button(
        "下载本次知识问答证据 JSON",
        json.dumps(safe_rag_export, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="retail_rag_evidence.json",
        mime="application/json",
    )
if selected_submit:
    question = f"{selected_age}岁{selected_gender}占{selected_scope}消费额多少？"
    submitted = True

if submitted:
    chosen = question.strip() or example
    try:
        with st.spinner("正在查询已核验的指标…"):
            active_mode = "rule" if selected_submit else query_mode
            started = time.perf_counter()
            if active_mode == "model":
                count = st.session_state.get("model_attempts", 0)
                if count >= 5:
                    response = {"status": "model_error", "answer": "本会话已达5次模型提交上限，请切换规则模式。此上限不是跨会话的费用保护。", "error_code": "session_limit"}
                elif not os.environ.get("DEEPSEEK_API_KEY"):
                    response = {"status": "model_error", "answer": "未配置密钥，本次未调用模型。请切换规则模式，或从已配置密钥的终端启动。", "error_code": "missing_api_key"}
                else:
                    st.session_state["model_attempts"] = count + 1
                    response = controlled_query.answer(chosen, mode="model")
            else:
                response = assistant.answer(chosen)
            response["ui_mode"] = active_mode
            response["ui_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
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
    origin = "受控模型模式" if response.get("ui_mode") == "model" else "规则模式 / 默认概览"
    if response.get("decision_source") == "program_guard":
        origin = "程序条件校验 · 本次未调用模型"
    st.caption(f"本条结果来源：{origin}。切换模式不会自动重新执行旧问题。")
    interpreted = condition_rows(response)
    if interpreted:
        with st.expander("系统理解的条件 · 请核对年龄、性别和分母", expanded=response.get("ui_mode") == "model"):
            st.dataframe(pd.DataFrame(interpreted), hide_index=True, width="stretch")
            st.caption("如果理解不符合你的意图，请改写完整问题重新查询。当前没有多轮条件记忆，不能只说“换成她们”。")
    if response.get("ui_mode") == "model":
        with st.expander("查看问题理解、耗时与用量", expanded=True):
            if "plan" in response:
                st.write("已校验的查询计划（模型不生成 SQL）：")
                st.json(response["plan"])
            telemetry = response.get("telemetry", {})
            st.write(f"本次端到端耗时：{response.get('ui_elapsed_ms', 0) / 1000:.2f} 秒")
            if telemetry.get("usage"):
                st.write("提供方实际返回的用量：")
                st.json(telemetry["usage"])
            elif response.get("model_called") is False:
                st.caption("程序提前返回，未发送模型请求。")
            else:
                st.caption("未获得提供方用量，不能将未知费用当作零费用。")
            if response.get("error_code"):
                st.code(response["error_code"], language="text")
    if response["status"] == "answered":
        st.subheader("分析结论")
        st.info(response["answer"])
        top = response["evidence"][0]
        cards = st.columns(3)
        selected = response.get("mode") == "selected"
        cards[0].metric("查询客群用户数" if selected else "排名第一客群用户数", f"{top['user_count']:,}")
        amount = top["total_purchase"]
        compact_amount = f"{amount / 100000000:,.2f} 亿" if amount >= 100000000 else f"{amount / 10000:,.2f} 万" if amount >= 10000 else f"{amount:,}"
        cards[1].metric("客群累计消费额 · 原始单位", compact_amount, help=f"完整金额：{amount:,}。万/亿仅缩写数量，不代表人民币；完整值见明细和下载。")
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
    elif response["status"] == "model_error":
        st.error(response["answer"])
        st.caption("没有静默降级或自动重试。可以在侧栏选择规则模式，再点击查询。")
    else:
        st.warning(response["answer"])
    st.download_button("下载本次查询凭据 JSON", query_receipt(chosen, response).encode("utf-8"), file_name="retail_query_receipt.json", mime="application/json")
    st.caption("凭据包含本次问题、结果、条件与来源；仅下载到本机，不代表服务器已持久化审计。分享前确认问题中没有敏感内容。")

if overview["status"] == "answered":
    render_customer_analysis(overview)

with st.expander("项目证据：规则版与模型路径如何验收？"):
    st.write("冻结验收v1共20题：规则版10/20符合预期；模型＋程序校验20/20，其中19题经过模型、1题由程序直接澄清；6道应答题的目标金额与比例核验一致。")
    st.caption("AI编写的小规模验收集，不是生产准确率或外部第三方评测。拒答与澄清目前主要核验状态，文本质量仍需人工复核。公开版与本地模型版的可用功能不同。")
    evidence_report = ROOT / "reports/holdout_v1_report.md"
    if evidence_report.exists():
        st.download_button("下载验收方法与结果", evidence_report.read_bytes(), file_name="holdout_v1_report.md", mime="text/markdown")

with st.expander("项目证据：RAG 如何评测与迭代？"):
    st.write("关键词检索开发集12/12；真实模型RAG v1人工复核11/12。失败题R10遗漏token统计范围，保留失败后升级提示词v2，定向回归通过。")
    st.caption("题目是可见开发集，不是外部独立评测。R04曾因同义表达触发自动评分假阴性；R06首次批次出现模型错误，恢复运行成功。页面不把回归结果包装成生产准确率。")
    rag_review = ROOT / "reports/rag_dev_review.md"
    if rag_review.exists():
        st.download_button("下载 RAG 评测与人工复核", rag_review.read_bytes(), file_name="rag_dev_review.md", mime="text/markdown")

with st.sidebar:
    st.divider()
    st.subheader("本次会话查询")
    for item in st.session_state.get("query_history", [])[:5]:
        status_label = {"answered": "已查询", "clarify": "待澄清", "unsupported": "暂不支持", "definition": "口径说明", "error": "查询异常"}.get(item["状态"], item["状态"])
        st.caption(f"• {item['问题']} · {status_label}")
    st.caption("仅保存在当前会话，不是企业审计日志。")
