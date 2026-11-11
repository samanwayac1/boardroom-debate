import copy
import json
import socket
import threading
import time
from pathlib import Path
import pytest
from boardroom.engine import Runner
from boardroom.models import validate_output
from boardroom.providers import Provider, Meter, BudgetExceeded
from boardroom.demo import response
from boardroom.exports import docx_bytes, pdf_bytes, markdown

CASE=json.loads((Path(__file__).parents[1]/'data/sample_case.json').read_text())

def wait_for(fn,timeout=10):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if fn(): return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for state')

def finish(r):
    handled=set()
    while r.status not in ('complete','failed','stopped'):
        s=r.snapshot(); token=(s['waiting'],s['round'])
        if s['waiting'] and token not in handled:
            handled.add(token)
            if s['waiting']=='frame': r.answer({'question':CASE['question'],'options':CASE['options']})
            elif s['waiting']=='debate': r.answer({'challenge':'Test distributor downside.'})
            else: r.answer({'disposition':'Accept','recommendation':'Conditional-go','summary':'Approve a gated pilot.','note':'Test review.'})
        if r.thread: r.thread.join(.03)
    assert r.status=='complete',r.stage


def test_demo_offline_full_flow_and_exports(monkeypatch):
    def deny(*a,**kw): raise AssertionError('Demo attempted networking')
    monkeypatch.setattr(socket.socket,'connect',deny)
    r=Runner(CASE,{},Provider('demo')); r.start(); finish(r)
    p=r.export()
    assert len(p['transcript'])==11
    assert len(p['scorecard'])==4
    assert any(e['kind']=='human_response' and e['checkpoint']=='final' for e in p['events'])
    assert docx_bytes(p).startswith(b'PK')
    assert pdf_bytes(p).startswith(b'%PDF')
    assert 'Risk Officer' in markdown(p)
    assert 'CANNED' in markdown(p)


def test_round_cap_and_disabled_agents():
    case=copy.deepcopy(CASE); case.update(rounds=1,agents=['CFO'],researcher=False)
    r=Runner(case,{},Provider('demo')); r.start(); finish(r)
    assert [h['role'] for h in r.history]==['Moderator','CFO','Moderator']
    assert len(r.scorecard())==1
    assert r.round==1


def test_pause_step_and_stop():
    r=Runner(CASE,{},Provider('demo')); r.start(step=True)
    wait_for(lambda:r.waiting=='frame')
    r.answer({'question':'Confirmed question?','options':['Pilot','Defer']})
    wait_for(lambda:r.status=='paused')
    before=len(r.history); r.step()
    wait_for(lambda:len(r.history)>before)
    wait_for(lambda:r.status=='paused')
    r.stop(); r.thread.join(3)
    assert r.status=='stopped'
    assert not r.thread.is_alive()


def test_malformed_output_retries_and_unknown_sources():
    class Broken(Provider):
        calls=0
        def call(self,text,role,phase,stop,context):
            self.calls+=1
            raw=response(role,phase,context); raw['summary']['source']='invented'
            return raw
    p=Broken('demo'); r=Runner(CASE,{},p); r.start(); r.thread.join(4)
    assert p.calls==3
    assert r.status=='failed'
    assert r.nodes['Moderator']['status']=='failed'


def test_recovery_after_bad_json():
    class Once(Provider):
        calls=0
        def call(self,text,role,phase,stop,context):
            self.calls+=1
            if self.calls==1: raise ValueError('Malformed JSON')
            return response(role,phase,context)
    p=Once('demo'); r=Runner(CASE,{},p); r.start(); finish(r)
    assert p.calls==12


def test_secret_not_in_export():
    p=Provider('demo',key='TEST_ONLY_SECRET_abc123')
    r=Runner(CASE,{},p); r.start(); finish(r)
    assert 'TEST_ONLY_SECRET_abc123' not in json.dumps(r.export())
    assert p._key==''


def test_parallel_cost_reservations_are_atomic():
    meter=Meter(input_rate=100,output_rate=100,cap=2)
    reservation=meter.reserve('test',1)
    with pytest.raises(BudgetExceeded): meter.reserve('test',1)
    meter.settle(reservation,(10,10))
    assert meter.snapshot()['reserved_usd']==0
    assert meter.snapshot()['estimated_cost_usd']==.002


def test_manual_handoff_and_cancel():
    p=Provider('chatgpt'); stop=threading.Event(); result=[]
    ctx=Runner(CASE,{},Provider('demo')).context()
    t=threading.Thread(target=lambda:result.append(p.call('prompt','Moderator','frame',stop,ctx)))
    t.start(); wait_for(lambda:bool(p.handoffs()))
    request=p.handoffs()[0]
    p.submit(request['id'],json.dumps(response('Moderator','frame',ctx)))
    t.join(2)
    assert result[0]['phase']=='frame'
    assert p.handoffs()==[]


def test_round_agents_share_prior_snapshot():
    r=Runner(CASE,{},Provider('demo')); r.start(); finish(r)
    opening=[h for h in r.history if h['phase']=='opening']
    assert all(h['input']['prior_messages']==opening[0]['input']['prior_messages'] for h in opening)
    rebuttals=[h for h in r.history if h['phase']=='rebuttal']
    assert all(len([v for v in h['input']['prior_messages'] if v['phase']=='opening'])==4 for h in rebuttals)
