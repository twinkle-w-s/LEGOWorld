import asyncio
import base64
import io
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image


def text(result):
    assert not result.isError, result
    return json.loads(next(c.text for c in result.content if c.type == "text"))


def test_stdio_script_batch_graph_images_export_and_reimport(tmp_path, real_assets):
    script = tmp_path / "build.py"
    script.write_text("""from brickagent import Assembly,move
def build():
    unit=Assembly('unit')
    lower=unit.add('3001',color='red')
    unit.attach('3005',to=lower.stud[0],by=('hole',0),color='yellow')
    model=Assembly('mcp_scene')
    model.add(unit)
    model.add(unit,pose=move(120,0,0))
    return model
""",encoding="utf-8")

    async def exercise():
        parameters=StdioServerParameters(command=sys.executable,
            args=['-X','utf8','-m','legoworld','serve','--workspace',str(tmp_path)],env=dict(os.environ))
        async with stdio_client(parameters) as (reader,writer):
            async with ClientSession(reader,writer) as client:
                await client.initialize()
                tools={t.name for t in (await client.list_tools()).tools}
                assert {'run_build_script','apply_edits','get_model_tree','get_connection_graph','render_view','export_model'} <= tools
                first=text(await client.call_tool('create_model',{'name':'wire','expected_revision':0}))
                built=text(await client.call_tool('run_build_script',{'path':str(script),'expected_revision':first['revision']}))
                assert built['ok'] and built['validation']['parts']==4
                assert not built['validation']['exportable']
                tree=text(await client.call_tool('get_model_tree',{'depth':3}))
                leaf=next(n for n in tree['nodes'] if n.get('part_id')=='3005')
                edited=text(await client.call_tool('apply_edits',{'expected_revision':tree['revision'],
                    'operations':[{'op':'recolor','node_id':leaf['id'],'color':'blue'}]}))
                assert edited['ok']
                graph=text(await client.call_tool('get_connection_graph',{}))
                assert graph['edge_count']==2 and len(graph['components'])==2
                review=await client.call_tool('review_model',{'note':'Wire image'})
                assert not review.isError,review
                images=[c for c in review.content if c.type=='image']
                assert images
                with Image.open(io.BytesIO(base64.b64decode(images[0].data))) as picture:
                    assert picture.size==(1200,940)
                exported=text(await client.call_tool('export_model',{}))
                assert exported['ok'] and exported['parts']==4
                imported=text(await client.call_tool('load_model',{'path':exported['mpd'],'expected_revision':edited['revision']}))
                assert imported['ok']
                assert imported['validation']['graph']['edges']==2
    asyncio.run(asyncio.wait_for(exercise(),timeout=90))
