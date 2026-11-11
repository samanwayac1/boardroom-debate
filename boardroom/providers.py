import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4
from .models import AgentOutput

class Cancelled(Exception): pass
class ProviderError(Exception): pass
class BudgetExceeded(ProviderError): pass

def parse_json(text):
    text = text.strip()
    if text.startswith('```'):
        lines=text.splitlines()
        text='\n'.join(lines[1:-1])
    return json.loads(text)

class Meter:
    def __init__(self, input_rate=0.4, output_rate=1.6, cap=1.0):
        self.input_rate=input_rate; self.output_rate=output_rate; self.cap=cap
        self.input_tokens=0; self.output_tokens=0; self.cost=0.0; self.reserved=0.0
        self.lock=threading.Lock(); self.estimated=False
    def reserve(self, text, max_output):
        # Conservative UTF-8 byte upper estimate plus schema/protocol overhead.
        tokens=len(text.encode('utf-8'))+16384
        amount=(tokens*self.input_rate + max_output*self.output_rate)/1e6
        with self.lock:
            if self.cost + self.reserved + amount > self.cap:
                raise BudgetExceeded('Cost cap reached. Export this run, then start with a higher cap or shorter input.')
            self.reserved+=amount
        return amount, tokens
    def settle(self, reservation, usage=None):
        amount, guessed=reservation
        with self.lock:
            self.reserved=max(0, self.reserved-amount)
            if usage is None:
                self.cost+=amount; self.input_tokens+=guessed; self.estimated=True
            else:
                i,o=usage
                self.input_tokens+=i; self.output_tokens+=o
                self.cost+=(i*self.input_rate+o*self.output_rate)/1e6
    def snapshot(self):
        with self.lock:
            return dict(input_tokens=self.input_tokens, output_tokens=self.output_tokens,
                        estimated_cost_usd=round(self.cost,6), reserved_usd=round(self.reserved,6),
                        estimated_usage=self.estimated, cap_usd=self.cap,
                        input_rate_per_million=self.input_rate, output_rate_per_million=self.output_rate)

class Provider:
    """Credentials stay in this per-session object, never in exports or graph state."""
    def __init__(self, kind, model='', key='', meter=None, local_cli=False):
        self.kind=kind; self.model=model; self._key=key; self.meter=meter or Meter()
        self.local_cli=local_cli; self.pending={}; self.lock=threading.Lock()
    def clear(self): self._key=''
    def handoffs(self):
        with self.lock: return [dict(id=k, prompt=v['prompt'], role=v['role'], phase=v['phase']) for k,v in self.pending.items() if not v['event'].is_set()]
    def submit(self, request_id, text):
        parse_json(text)  # quick feedback; full schema validation occurs in the engine
        with self.lock:
            p=self.pending.get(request_id)
            if p is None: raise ValueError('This request has expired.')
            p['answer']=text; p['event'].set()
    def call(self, text, role, phase, stop, context):
        if stop.is_set(): raise Cancelled()
        if self.kind == 'demo':
            from .demo import response
            stop.wait(.35)
            if stop.is_set(): raise Cancelled()
            return response(role,phase,context)
        if self.kind == 'chatgpt' and not self.local_cli:
            request_id=uuid4().hex
            item={'prompt':text,'role':role,'phase':phase,'event':threading.Event(),'answer':''}
            with self.lock: self.pending[request_id]=item
            try:
                deadline=time.monotonic()+1800
                while not item['event'].wait(.2):
                    if stop.is_set(): raise Cancelled()
                    if time.monotonic()>deadline: raise ProviderError('ChatGPT handoff timed out after 30 minutes. Start a new run.')
                return parse_json(item['answer'])
            finally:
                with self.lock: self.pending.pop(request_id,None)
        if self.kind == 'chatgpt': return self._codex(text,stop)
        reservation=self.meter.reserve(text,3000)
        usage=None
        try:
            if self.kind == 'openai':
                from openai import OpenAI
                with OpenAI(api_key=self._key,base_url='https://api.openai.com/v1',timeout=90,max_retries=0) as client:
                    r=client.responses.create(model=self.model,input=text,store=False,max_output_tokens=3000,
                        text={'format':{'type':'json_schema','name':'board_position','strict':True,'schema':AgentOutput.model_json_schema()}})
                if r.usage: usage=(r.usage.input_tokens,r.usage.output_tokens)
                result=r.output_text
            elif self.kind == 'anthropic':
                from anthropic import Anthropic
                with Anthropic(api_key=self._key,base_url='https://api.anthropic.com',timeout=90,max_retries=0) as client:
                    r=client.messages.create(model=self.model,max_tokens=3000,messages=[{'role':'user','content':text}])
                usage=(r.usage.input_tokens,r.usage.output_tokens)
                result='\n'.join(b.text for b in r.content if b.type=='text')
            else: raise ProviderError('Choose a supported provider.')
        except ProviderError: raise
        except Exception as exc:
            code=getattr(exc,'status_code',None)
            if code in (401,403): msg='Authentication or access failed. Check your own key and model permissions.'
            elif code==429: msg='Provider quota or rate limit reached. Check billing and wait before retrying.'
            elif code==400 or code==404: msg='Provider rejected this model or structured-output request. Check the model ID and input size.'
            else: msg='Provider request failed or timed out. Check connectivity and provider status.'
            raise ProviderError(msg) from None
        finally: self.meter.settle(reservation,usage)
        if stop.is_set(): raise Cancelled()
        return parse_json(result)

    def _codex(self,text,stop):
        binary=shutil.which('codex')
        if not binary: raise ProviderError('Codex CLI is missing on the app server. Run locally, install Codex, and complete the README login steps.')
        env=os.environ.copy()
        for k in ('OPENAI_API_KEY','CODEX_API_KEY','ANTHROPIC_API_KEY','OPENAI_BASE_URL','OPENAI_ORG_ID','OPENAI_PROJECT_ID'):
            env.pop(k,None)
        env['CODEX_HOME']=str(Path.home()/'.boardroom-codex')
        # A dedicated login avoids loading the user's usual plugins, MCP servers or project files.
        home=Path(env['CODEX_HOME'])
        if not home.exists(): raise ProviderError('Dedicated ChatGPT login is missing. Follow README: CODEX_HOME=~/.boardroom-codex codex login.')
        config=home/'config.toml'
        if config.exists():
            import tomllib
            try: settings=tomllib.loads(config.read_text())
            except Exception: raise ProviderError('Dedicated Codex configuration is invalid.') from None
            if any(settings.get(x) for x in ('mcp_servers','plugins','hooks','model_providers','profiles')):
                raise ProviderError('Use a clean dedicated Codex home without MCP servers, plugins, hooks or custom providers.')
        try:
            status=subprocess.run([binary,'login','status'],env=env,capture_output=True,text=True,timeout=15)
        except Exception: raise ProviderError('Could not check Codex login. Run codex login with the dedicated CODEX_HOME.') from None
        if status.returncode or 'chatgpt' not in (status.stdout+status.stderr).lower():
            raise ProviderError('Codex is not signed in with ChatGPT. Complete the dedicated login in README; API-key login is not accepted here.')
        with tempfile.TemporaryDirectory(prefix='boardroom-') as folder:
            root=Path(folder); schema=root/'schema.json'; output=root/'response.json'
            schema.write_text(json.dumps(AgentOutput.model_json_schema()),encoding='utf-8')
            args=[binary,'exec','--ephemeral','--ignore-user-config','--skip-git-repo-check','--sandbox','read-only',
                  '-c','forced_login_method="chatgpt"','-c','model_provider="openai"',
                  '-c','features.shell_tool=false','-c','web_search="disabled"',
                  '-c','history.persistence="none"','--output-schema',str(schema),'-o',str(output),'-']
            if self.model.strip(): args[2:2]=['--model',self.model.strip()]
            p=None
            try:
                p=subprocess.Popen(args,cwd=folder,env=env,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True)
                p.stdin.write(text); p.stdin.close()
                deadline=time.monotonic()+180
                while p.poll() is None:
                    if stop.wait(.1): p.terminate(); raise Cancelled()
                    if time.monotonic()>deadline: p.terminate(); raise ProviderError('Codex timed out. Check model availability and ChatGPT usage limits.')
                if p.returncode or not output.exists():
                    raise ProviderError('Codex failed. Update the CLI, check dedicated ChatGPT login, model access and subscription limits. No API fallback was used.')
                return parse_json(output.read_text(encoding='utf-8'))
            except (OSError,UnicodeError): raise ProviderError('Could not run Codex. Check CLI installation and local permissions.') from None
            finally:
                if p and p.poll() is None:
                    p.kill(); p.wait(timeout=5)
