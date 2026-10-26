# Retail Insight RAG 知识库

本目录保存可由知识问答路径检索和引用的批准文档。结构化经营指标仍由 SQL 计算，不从知识库正文中推断实时数值。

## 当前文档

| 文档 ID | 文件 | 内容 |
| --- | --- | --- |
| KB-METRIC-001 | `metric_dictionary.md` | 指标定义、公式与分母 |
| KB-DATA-001 | `data_boundaries.md` | 数据来源、字段缺失与分析边界 |
| KB-PRODUCT-001 | `product_guide.md` | 支持范围、查询路径与失败处理 |
| KB-EVAL-001 | `evaluation_notes.md` | 评测事实与可解释边界 |

每份文档必须保留 `doc_id`、`title`、`version`、`status` 和 `updated` 元数据。只有 `status: approved` 的文档可以进入检索。标题章节作为首版检索粒度，回答需展示文档 ID、标题和章节。

知识库内容变更后应重新运行：

```powershell
python .\scripts\check_knowledge_base.py
```

当前关键词检索基线位于 `rag_retriever.py`。它按章节检索批准文档，返回文档 ID、标题、章节、版本、来源和匹配分数；相关度不足时返回 `unsupported`。运行回归检查：

```powershell
python .\scripts\check_rag_retriever.py
```

单题检索示例：

```powershell
python .\rag_retriever.py "购买记录数是不是订单数？"
```

受控生成回答位于 `controlled_rag.py`。它只把命中的批准片段发给模型，并校验模型返回的引用 ID；伪造引用或格式错误不会展示为成功回答。真实单题调用需要在本机配置 `DEEPSEEK_API_KEY`：

```powershell
python .\controlled_rag.py "购买记录数是不是订单数？"
```

开发评测题位于 `evals/rag_dev.json`。受控传输与引用校验已通过模拟测试；真实模型v1人工复核为11/12，失败题保留后以v2定向回归通过。详细记录见 `reports/rag_dev_review.md`。这些题是可见开发集，不能描述为独立评测或生产准确率。

关键词检索开发集可免费运行：

```powershell
python .\scripts\evaluate_rag.py --mode retrieval --limit 12
```

2026-10-26 的当前开发版本在同一批题上通过 12/12 自动检索检查；该批问题可见且已用于增加 `tokens`→“用量”的透明同义词映射，因此只能作为开发集结果。真实模型目前仅完成单题冒烟调用，批量回答仍需运行并人工复核。

