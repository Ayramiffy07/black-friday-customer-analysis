# RAG 开发评测保存故障记录

日期：2026-10-26  
范围：R04–R12 首次真实模型批次

## 事件

九题均已运行，但固定输出文件 `reports/rag_dev_model.csv` 当时正在 Excel 中打开。Windows 文件锁导致脚本在批次结束后写入失败，抛出 `PermissionError`。旧的 R01–R03 文件未损坏，但本批完整回答、引用详情、错误代码和 token 用量未保存。

## 截图可确认的首次状态

| 题目 | 截图中的状态 | 引用检查 | 自动结果 |
| --- | --- | --- | --- |
| R04 | answered | True | False |
| R05 | answered | True | True |
| R06 | model_error | False | False |
| R07 | answered | True | True |
| R08 | answered | True | False |
| R09 | answered | True | True |
| R10 | answered | True | False |
| R11 | unsupported | True | True |
| R12 | unsupported | True | True |

以上只能作为运行状态证据，不能补写未保存的回答内容或用量，也不能用恢复运行覆盖 R06 的首次失败。

## 修复

`scripts/evaluate_rag.py` 已改为在调用前创建唯一时间戳归档，并在每题完成后更新归档。固定“最新结果”文件变为尽力写入；若被 Excel 锁定，脚本警告但保留完整归档。

后续恢复运行需明确标记为保存故障后的第二次运行，不得将它冒充首次结果或用来删除首次失败。

