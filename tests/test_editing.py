from copy import deepcopy
import json

import pytest

from legoworld.backend import b, pack, unpack
from legoworld.build import expose_port, require_contact
from legoworld.catalog import asset_status, search
from legoworld.document import entries, flat_records
from legoworld.editing import apply_operations, integrate
from legoworld.geometry import render_png
from legoworld.precision import validate_document


def test_add_component_mount_and_instance_transforms_keep_port_frames(real_assets):
    root = b.Assembly('base')
    root.add('3001', color='red')
    doc = pack(root)
    base = flat_records(doc)[0]['id']
    unit = b.Assembly('detail')
    lower = unit.add('3005', color='yellow')
    expose_port(unit, 'bottom', lower.hole[0])
    result, info = integrate(doc, unit, 'add_component', mount={
        'by':'bottom', 'to':{'node_id':base,'type':'stud','index':0}})
    assert validate_document(result)['batch_valid']
    assert len(b.attachments(unpack(result))) == 1
    # Full source orientation is honored even if its pre-mount local pose is rotated.
    second, _ = integrate(doc, unit, 'add_component', placement={'t':[80,10,20],'rot':b.spin(b.UP,90).rot},
        mount={'by':'bottom','to':{'node_id':base,'type':'stud','index':0},'orient':{'rot':b.ID.rot}})
    assert validate_document(second)['batch_valid']
    npart = b.parts(unpack(second))[1]
    assert tuple(npart.rot) == b.ID.rot
    made, _ = apply_operations(result, [{'op':'instance','source_id':info['target_id'],'pose':{'t':[120,0,0]}}])
    assert validate_document(made)['batch_valid']


def test_replacement_requires_explicit_connector_mapping(real_assets):
    model = b.Assembly('replace')
    base=model.add('3001');model.attach('3005',to=base.stud[0],by=('hole',0))
    doc=pack(model); leaf=flat_records(doc)[1]['id']
    with pytest.raises(ValueError,match='connector_map'):
        apply_operations(doc,[{'op':'replace','node_id':leaf,'part_id':'3004'}])


def test_required_second_support_survives_json_roundtrip(real_assets):
    model=b.Assembly('bridge')
    left=model.add('3005')
    right=model.add('3005',pose=b.move(40,0,0))
    span=model.attach('3623',to=left.stud[0],by=('hole',0),orient=b.ID)
    require_contact(model,span.hole[-1],right.stud[0])
    doc=pack(model)
    assert len(b.attachments(unpack(json.loads(json.dumps(doc)))))==2
    assert validate_document(doc)['batch_valid']


def test_empty_and_malformed_documents_do_not_export(real_assets):
    empty=pack(b.Assembly('empty'))
    assert not validate_document(empty,True)['exportable']
    with pytest.raises(ValueError,match='target_id=root'):
        integrate(empty,b.Assembly('replacement'),'replace_model',target_id='not-root')
    for bad_id in ('../outside','/outside',''):
        bad=deepcopy(empty);bad['model_id']=bad_id
        with pytest.raises(ValueError,match='project ID'):
            unpack(bad)


def test_asset_filter_checks_recursive_dependencies_and_invalidates_missing_file(monkeypatch,tmp_path):
    root=tmp_path/'ldraw';(root/'parts').mkdir(parents=True);(root/'p').mkdir()
    (root/'parts/3001.dat').write_text('1 16 0 0 0 1 0 0 0 1 0 0 0 1 child.dat\n')
    colliders=tmp_path/'colliders/cvx';colliders.mkdir(parents=True)
    (colliders/'3001.cvx.obj').write_text('placeholder')
    monkeypatch.setenv('LDRAW_LIBRARY_PATH',str(root))
    monkeypatch.setenv('BRICKNET_DATA',str(colliders.parent))
    assert not asset_status('3001')['available']
    assert search('3001',limit=1)['parts']==[]
    (root/'p/child.dat').write_text('3 16 0 0 0 10 0 0 0 10 0\n')
    assert asset_status('3001')['available']
    (root/'p/child.dat').unlink()
    assert not asset_status('3001')['available']


def test_mesh_renderer_supports_snot_arbitrary_pose_and_selected_component(real_assets):
    model=b.Assembly('render')
    base=model.add('87087',color='red')
    model.attach('6141',to=base.open[0],by=('tube',0),color='yellow')
    scene=b.Assembly('scene');scene.add(model,pose=b.spin(b.UP,37))
    doc=pack(scene)
    component=next(k for k,v in entries(doc).items() if k!='root' and v['assembly'])
    a=render_png(doc,35,28,300,250,[component])
    assert a.startswith(b'\x89PNG') and a!=render_png(doc,150,10,300,250)
