from copy import deepcopy
import json

from legoworld.backend import b
from legoworld.document import entries, flat_records
from legoworld.project import Project


BUILD = """from brickagent import Assembly, move
from legoworld.build import expose_port
def build(height=2):
    unit = Assembly('tower')
    base = unit.add('3005', color='tan')
    expose_port(unit, 'bottom', base.hole[0])
    top = base
    for _ in range(height-1):
        top = unit.attach('3005', to=top.stud[0], by=('hole',0), color='red')
    scene = Assembly('towers')
    floor = scene.add('3001', color='dark gray')
    scene.attach(unit, to=floor.stud[0], by=base.hole[0])
    scene.add(unit, pose=move(120,0,0))
    return scene
"""


def run(project, path, **kwargs):
    return project.mutate('build', project.revision, path=path, parameters={},
                          mode='replace_model', target_id='root', **kwargs)


def test_script_edit_persistence_stale_and_failed_candidate(project, script):
    path = script(BUILD)
    result = run(project, path)
    assert result['ok'], result
    initial = deepcopy(project.document)
    leaves = flat_records(initial)
    changed = project.mutate('edit', project.revision, operations=[
        {'op':'recolor','node_id':leaves[2]['id'],'color':'green'}])
    assert changed['ok']
    assert project.mutate('edit', initial['revision'], operations=[])['error']['type'] == 'stale_revision'
    reloaded = Project(project.workspace)
    assert reloaded.document == project.document
    before = deepcopy(project.document)
    failed = project.mutate('edit', project.revision, operations=[
        {'op':'add','part_id':leaves[0]['stem'],'pose':{'t':leaves[0]['pos'],'rot':leaves[0]['rot']}}])
    assert not failed['ok'] and failed['candidate_id']
    assert project.document == before
    assert project.selected_document(failed['candidate_id']) != before
    assert project.render(failed['candidate_id']).startswith(b'\x89PNG')


def test_named_port_replacement_preserves_external_join_and_other_copy(project, script):
    assert run(project, script(BUILD))['ok']
    parts = flat_records(project.document)
    assert project.mutate('edit', project.revision, operations=[
        {'op':'recolor','node_id':parts[2]['id'],'color':'green'}])['ok']
    components = [i for i,v in entries(project.document).items() if v['assembly'] and i!='root']
    target, other = components
    other_before = [p for p in flat_records(project.document) if p['id'].startswith(other+'/')]
    replacement = script("""from brickagent import Assembly
from legoworld.build import expose_port
def build():
    m=Assembly('new tower')
    p=m.add('3005',color='blue')
    expose_port(m,'bottom',p.hole[0])
    for _ in range(3):
        p=m.attach('3005',to=p.stud[0],by=('hole',0),color='yellow')
    return m
""", 'replacement.py')
    result = project.mutate('build', project.revision, path=replacement, parameters={},
                            mode='replace_component', target_id=target)
    assert result['ok'], result
    assert result['details']['replacement_discards_local_edits']
    assert [p for p in flat_records(project.document) if p['id'].startswith(other+'/')] == other_before
    assert len(result['details']['invalidated_ids']) == 2
    assert project.validate()['batch_valid']
    before=deepcopy(project.document)
    missing=script('from brickagent import Assembly\ndef build():\n m=Assembly("bad");m.add("3005");return m\n','missing.py')
    failed=project.mutate('build',project.revision,path=missing,parameters={},mode='replace_component',target_id=target)
    assert not failed['ok'] and 'named port' in failed['error']['message']
    assert project.document==before


def test_worker_exception_timeout_crash_and_invalid_import_preserve_state(project, script, tmp_path):
    assert project.mutate('edit',0,operations=[{'op':'add','part_id':'3001','color':'red'}])['ok']
    before=deepcopy(project.document)
    for name,source,timeout,kind in [
        ('exception.py','def build():\n raise RuntimeError("bad build")\n',120,'RuntimeError'),
        ('timeout.py','import time\ndef build():\n time.sleep(10)\n',2,'worker_timeout'),
        ('crash.py','import os\nos._exit(7)\n',120,'worker_exit'),
        ('invalid.py','from brickagent import Assembly,Pose\ndef build():\n m=Assembly("bad");m.add("3001",pose=Pose(t=(float("nan"),0,0)));return m\n',120,'ValueError')]:
        failed=project.mutate('build',project.revision,timeout,path=script(source,name),parameters={},mode='replace_model',target_id='root')
        assert not failed['ok'] and failed['error']['type']==kind,failed
        assert project.document==before
    bad=tmp_path/'bad.mpd'
    bad.write_text('0 bad\n1 4 0 0 0 2 0 0 0 1 0 0 0 1 3001.dat\n')
    assert not project.mutate('import',project.revision,path=str(bad))['ok']
    assert project.document==before


def test_checkpoint_restore_keeps_mcp_edits_as_new_revision(project, script):
    assert run(project,script(BUILD))['ok']
    leaf=flat_records(project.document)[0]['id']
    assert project.mutate('edit',project.revision,operations=[{'op':'recolor','node_id':leaf,'color':'blue'}])['ok']
    checkpoint=project.save_checkpoint()
    snapshot=deepcopy(project.document)
    assert project.mutate('edit',project.revision,operations=[{'op':'recolor','node_id':leaf,'color':'yellow'}])['ok']
    revision=project.revision
    assert project.restore_checkpoint(checkpoint['checkpoint_id'],revision)['ok']
    assert project.revision==revision+1
    assert flat_records(project.document)==flat_records(snapshot)


def test_transaction_can_add_then_attach_with_aliases(project):
    result=project.mutate('edit',0,operations=[
        {'op':'add','part_id':'3001','color':'red','as':'base'},
        {'op':'add','part_id':'3005','color':'yellow','as':'top'},
        {'op':'attach','node_id':'$top','by':{'node_id':'$top','type':'hole','index':0},
         'to':{'node_id':'$base','type':'stud','index':0}}])
    assert result['ok'],result
    assert len(result['validation']['graph']['edges'])==1
    assert project.export()['ok']
