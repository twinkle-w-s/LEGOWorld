# V3 验证提示词

先让通用 agent 读取 skills/lego-builder/SKILL.md，并重连 LEGOWorld MCP。

## 验证混合构建

用 LEGOWorld V3 做一座约 150–250 件的双塔城门。先写 Python build()，用共享子组件构建两座塔，公开底部连接端口，并使用真实拱门和侧面灯饰。通过 MCP 执行脚本后，只用 apply_edits 调整其中一座塔的配色，确认另一座没有变化。查看四视图，修改一轮比例或细节，最后通过完整检查导出 IO、MPD、项目 JSON 和预览。

## 验证局部重建

先保存检查点。只重建左塔，把它增高一层，通过原有命名端口保留与底座的连接；右塔和此前对右塔的工具修改都要保留。刷新模型树，检查连接图和图片，再导出。若端口无法匹配，应解释失败并保留原模型。

## 快速确定性验证

运行 python -m legoworld demo-v3。查看 outputs/v3_modular_castle 中的模型、预览和 validation.json。该命令不调用 LLM，验证执行链路。
