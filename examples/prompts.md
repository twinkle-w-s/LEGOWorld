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
# 第二版：精细零件与几何反馈

请用 LEGOWorld MCP 搭建一座微型城堡门楼，约 40–80 件。两侧使用圆砖和圆锥屋顶，中央使用真实拱门零件，增加跳线板和圆形装饰。先查询可用零件和连接点，使用 attach_part 或放置预检完成细节。只使用服务支持的直立凸点连接。

完成主体后调用 review_model，实际查看图片，检查拱洞、塔楼比例和配色；再用 render_view 排除大底板、放大建筑细节。根据图片修改一轮，消除穿插和悬空。确认碰撞后端是 bricknet、verified=true，再导出 IO/MPD。不要把离线 demo 当作你的自主设计结果。
