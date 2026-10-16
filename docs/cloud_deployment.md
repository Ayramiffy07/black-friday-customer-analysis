# Streamlit Community Cloud 部署

入口：app.py；分支：main；Python：3.12。依赖使用根目录 requirements.txt。

云端不包含原始 CSV 或本地数据库时，自动使用 reports/sql_customer_contribution.csv 的14个客群汇总快照，在内存 SQLite 执行 demo SQL。快照由脚本18从完整数据核验生成，不是模拟数据。仅覆盖现有客群贡献场景，不支持用户明细或实时数据。无需密钥。

本地设置 RETAIL_DEMO_MODE=1 可强制测试同一路径。运行 scripts/check_cloud_demo.py 检查本地与快照路径的指标一致性。

登录 https://share.streamlit.io ，创建应用，选择 Ayramiffy07/black-friday-customer-analysis、main、app.py。高级设置选 Python 3.12。子域名可尝试 ayra-retail-insight，是否可用以上线平台为准。不要将未验证的候选地址写入简历。

部署后用无痕窗口验证：全体排名、26–35岁女性占全体8.69%、占该年龄段21.80%、无效年龄请求澄清、日期问题拒答、CSV下载。线上URL确认可公开访问后，再加入README和简历。
