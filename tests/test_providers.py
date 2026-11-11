import threading
from pathlib import Path
from types import SimpleNamespace
import pytest
from boardroom.providers import Provider, Meter, ProviderError
from boardroom.models import AgentOutput


def test_openai_adapter_uses_fixed_endpoint_schema_no_storage(monkeypatch):
    import openai
    seen={}
    class Client:
        def __init__(self,**kw): seen.update(kw); self.responses=self
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def create(self,**kw):
            seen['request']=kw
            return SimpleNamespace(output_text='{"ok":true}',usage=SimpleNamespace(input_tokens=100,output_tokens=20))
    monkeypatch.setattr(openai,'OpenAI',Client)
    p=Provider('openai','gpt-4.1-mini','FAKE_ONLY',Meter(cap=5))
    assert p.call('prompt','CEO','opening',threading.Event(),{})=={'ok':True}
    assert seen['base_url']=='https://api.openai.com/v1'
    assert seen['max_retries']==0
    assert seen['request']['store'] is False
    assert seen['request']['text']['format']['schema']==AgentOutput.model_json_schema()
    assert p.meter.snapshot()['input_tokens']==100
    assert p.meter.snapshot()['reserved_usd']==0


def test_anthropic_adapter_and_safe_error(monkeypatch):
    import anthropic
    seen={}
    class Client:
        def __init__(self,**kw): seen.update(kw); self.messages=self
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def create(self,**kw):
            return SimpleNamespace(content=[SimpleNamespace(type='text',text='{"ok":true}')],usage=SimpleNamespace(input_tokens=70,output_tokens=10))
    monkeypatch.setattr(anthropic,'Anthropic',Client)
    p=Provider('anthropic','model','FAKE_ONLY',Meter(cap=5))
    assert p.call('prompt','CFO','opening',threading.Event(),{})['ok']
    assert seen['base_url']=='https://api.anthropic.com'
    class Broken(Client):
        def create(self,**kw): raise RuntimeError('do not expose FAKE_ONLY or provider body')
    monkeypatch.setattr(anthropic,'Anthropic',Broken)
    with pytest.raises(ProviderError) as err: p.call('prompt','CFO','opening',threading.Event(),{})
    assert 'FAKE_ONLY' not in str(err.value)
    assert 'provider body' not in str(err.value)


def test_missing_codex_is_friendly(monkeypatch):
    import boardroom.providers as mod
    monkeypatch.setattr(mod.shutil,'which',lambda name:None)
    p=Provider('chatgpt',local_cli=True)
    with pytest.raises(ProviderError,match='missing'): p.call('p','CEO','opening',threading.Event(),{})


def test_codex_adapter_forces_chatgpt_and_cleans_temporary_files(monkeypatch,tmp_path):
    import boardroom.providers as mod
    monkeypatch.setattr(mod.shutil,'which',lambda name:'/fake/codex')
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:tmp_path))
    (tmp_path/'.boardroom-codex').mkdir()
    monkeypatch.setenv('OPENAI_API_KEY','FAKE_API_CREDENTIAL')
    monkeypatch.setattr(mod.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout='Logged in using ChatGPT',stderr=''))
    seen={}
    class Sink:
        def write(self,text): seen['prompt']=text
        def close(self): pass
    class Process:
        def __init__(self,args,**kw):
            seen.update(args=args,**kw); self.stdin=Sink(); self.returncode=0
            Path(args[args.index('-o')+1]).write_text('{"ok":true}')
        def poll(self): return 0
    monkeypatch.setattr(mod.subprocess,'Popen',Process)
    assert Provider('chatgpt',local_cli=True).call('private evidence','CEO','opening',threading.Event(),{})['ok']
    assert '--ignore-user-config' in seen['args']
    assert '--ephemeral' in seen['args']
    assert 'forced_login_method="chatgpt"' in seen['args']
    assert 'features.shell_tool=false' in seen['args']
    assert 'OPENAI_API_KEY' not in seen['env']
    assert not Path(seen['cwd']).exists()
