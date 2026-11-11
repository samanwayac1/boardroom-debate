import time
from pathlib import Path
from streamlit.testing.v1 import AppTest
from boardroom.demo import response
from boardroom.providers import Provider

APP=Path(__file__).parents[1]/'app.py'

def button(at,label): return next(b for b in at.button if b.label==label)
def settle(at,waiting):
    end=time.monotonic()+10
    while time.monotonic()<end:
        at.run(timeout=20)
        assert not at.exception
        r=at.session_state['runner']
        if r.waiting==waiting or (waiting is None and r.status=='complete'): return
        time.sleep(.05)
    raise AssertionError('UI timed out')

def test_demo_ui_all_reviews_and_downloads(monkeypatch):
    original=Provider.call
    def instant(self,text,role,phase,stop,context):
        if self.kind=='demo': return response(role,phase,context)
        return original(self,text,role,phase,stop,context)
    monkeypatch.setattr(Provider,'call',instant)
    at=AppTest.from_file(str(APP)).run(timeout=20)
    assert not at.exception
    button(at,'▶ Demo Run').click().run(timeout=20)
    settle(at,'frame')
    button(at,'Confirm framing').click().run(timeout=20)
    settle(at,'debate')
    assert at.session_state['runner'].round==1
    button(at,'Apply feedback and continue').click().run(timeout=20)
    settle(at,'debate')
    assert at.session_state['runner'].round==2
    button(at,'Continue to memo').click().run(timeout=20)
    settle(at,'final')
    assert not at.exception
    assert len(at.session_state['docx'])>1000
    button(at,'Record board decision').click().run(timeout=20)
    settle(at,None)
    assert any('FINAL REVIEW RECORDED' in str(x.value) for x in at.markdown)
    assert len(at.session_state['pdf'])>1000
