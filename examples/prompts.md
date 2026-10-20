# First-run prompts

After connecting LEGOWorld MCP, have your agent read `skills/lego-builder/SKILL.md`.

## House

用 LEGOWorld 搭一座小房子：绿色底座、米黄色墙、红色阶梯屋顶和一个门洞，
约 100–200 块。先搭主体，再检查冲突和悬空；读取四视图，调整比例和配色。
最多迭代五轮，最终输出 Studio .io、MPD、预览图和检查报告。

## Watchtower

用普通砖和板搭一座灰色瞭望塔，带蓝色顶层装饰、入口和顶部垛口，约 150 块。
用 review_model 的图片比较塔身和底座比例，修复所有基础检查错误再导出。

## Follow-up edit

把刚才房子的屋顶改成深灰色，底座缩小一点。先保存检查点，修改后重新检查，
读取四视图确认没有切掉墙体或产生悬空，再导出新结果。
