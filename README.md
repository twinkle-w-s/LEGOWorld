# LEGOWorld V3

自然语言 → 外部通用 agent 编写 Python / 调用 MCP → BrickAgent 层级建模 → BrickNet 碰撞与连接图 → 多视图审查 → 局部精修 → Studio IO / MPD。

V3 使用 **一份可保存的层级模型**。Python 负责循环、参数和组件复用；MCP 保留搜索、连接点查询、批量编辑、预检、看图及导出。脚本执行和工具编辑都经过事务检查，失败时保留当前模型。

![264-piece modular castle](examples/v3_castle/detail.png)

[示例脚本](examples/builds/castle_v3.py) · [完整使用与迁移](docs/V3.md) · [验证记录](docs/VERIFICATION.md) · [第三方来源](THIRD_PARTY.md)

## 开始使用

在仓库根目录运行，推荐 Python 3.12：

```powershell
.\scripts\setup.ps1 -Python <Python3.12的完整路径>
.\.venv\Scripts\python.exe -X utf8 -m legoworld fetch-assets
.\.venv\Scripts\python.exe -X utf8 -m legoworld doctor
.\.venv\Scripts\python.exe -X utf8 -m legoworld demo-v3
```

依赖固定为 BrickAgent 0.1.0、BrickNet 0.1.1、PyBullet 3.2.7。Windows 的 PyBullet 可能需要 Visual Studio C++ Build Tools；本机已编译。新环境下载几何和碰撞资产后再建模；启动 MCP 不会自动下载。

`demo-v3` 生成 264 件城堡：共享塔楼、嵌套组件、侧面凸点灯饰、双支撑拱门、一次 MCP 等价批次改色，最后执行完整稳定性检查并导出。它是确定性工具链演示，不调用 LLM。会替换工作区的当前模型。

生成 MCP 配置参考，合并到 Claude Code 等客户端现有配置，然后重连服务：

```powershell
.\.venv\Scripts\python.exe -m legoworld mcp-config
```

本项目不调用模型 API，不需要设置 LLM API key。模型服务由外部 agent 的客户端配置。现有 `.claude/` 不由安装脚本改写。

## 推荐工作流

让 agent 读取 [lego-builder 指引](skills/lego-builder/SKILL.md)，通过 MCP 执行：

1. `get_model_tree` 读取当前 revision，必要时 `create_model`。
2. 搜索零件、查询真实连接点，在工作区写 `build.py`，实现 `build(**parameters) -> brickagent.Assembly`。
3. `run_build_script` 一次构建主体或一个组件；使用函数、循环及共享子组件减少往返。
4. `apply_edits` 批量改色、变换、连接或替换，`review_model` 返回原生四视图图片。
5. 修改脚本时明确选择重建整个模型、添加组件或替换某个组件。
6. `export_model` 通过完整检查后输出模型。

所有写操作携带 `expected_revision`；失败不会推进 revision。默认编辑一个组件副本只影响该副本。组件重建会替换目标内部的工具修改，其他部分保留。命名端口用于保留组件间指定连接。

## 检查与零件范围

碰撞使用 BrickNet 凸分解和 1 LDU 容差。连接图由 BrickAgent 递归展开后的世界姿态推断，支持原生凸点、侧面凸点、轴、夹子、铰链及球接头等连接；指定连接还必须满足精确配合。

每批检查碰撞、指定连接和上游库存约束；允许尚未落地的中间组件。最终导出增加 BrickAgent 刚体稳定性检查，多个稳定独立物体可以通过。报告中的 `batch_valid` 与 `exportable` 表示不同阶段。

搜索过滤零件几何的递归依赖和碰撞体。本机全量扫描的 14,441 种原生零件资产齐全；现有 60 种保留为 `common_only` 常用集合。资产齐全不代表每种零件及其所有连接组合都经过人工搭建验证。

## 文件与恢复

`outputs/project.json` 是当前完整状态，服务重启自动恢复。导出目录含：

```text
outputs/<作品名>/
  model.io             基础 Studio ZIP
  model.mpd            保留共享组件的原生 LDraw
  project.json         含端口、指定连接、脚本来源和 MCP 精修的完整快照
  preview.png
  validation.json
```

检查点、失败候选和审查分别位于 `outputs/checkpoints`、`outputs/candidates`、`outputs/reviews`。要完整继续编辑，优先加载 V3 JSON；MPD/IO 恢复几何与层级，并重新推断连接，不包含项目端口或指定连接意图。

## 开发与边界

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
.\.venv\Scripts\python.exe -X utf8 -m legoworld doctor --full
.\.venv\Scripts\python.exe -X utf8 scripts/benchmark_v3.py
```

资产路径仍通过 `LEGOWORLD_ASSETS`、`LDRAW_LIBRARY_PATH` 和 `BRICKNET_DATA` 注入。V2 的 AABB / boxes 回退及底部原点约定已取消；迁移时移除旧回退配置，改用原生 LDraw 坐标或导入旧 MPD。

脚本作为受信任本地代码执行；独立进程用于隔离异常、超时和原生崩溃，不能回滚任意文件副作用。构建函数应只创建模型。预览仍为 CPU 不透明平面着色；稳定性把连接分量视为刚体，不模拟凸点夹持力、关节受力或变形。基础 IO 不保存 Studio 说明书与 modelv2 元数据，Studio GUI 打开、编辑和另存仍需人工验收。

V2 保留在 `feat/v0.2-precision`（`33b17a0`）；V1 保留为 `v0.1.0`。不同版本应使用独立虚拟环境。
