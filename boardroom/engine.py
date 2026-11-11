import copy
import json
import operator
import os
import threading
import time
from datetime import datetime, timezone
from typing import Annotated, TypedDict
# No external traces, even if the hosting process has tracing defaults.
os.environ['LANGCHAIN_TRACING_V2']='false'
os.environ['LANGSMITH_TRACING']='false'
from langgraph.graph import StateGraph, START, END
from .finance import snapshots
from .models import ROLES, validate_output
from .prompts import prompt
from .providers import Cancelled, ProviderError

class BatchState(TypedDict):
    results: Annotated[list, operator.add]

class Runner:
    def __init__(self, case, sources, provider):
        self.case=copy.deepcopy(case); self.provider=provider
        self.sources=copy.deepcopy(sources)
        self.sources.update({'brief':{'label':'User decision brief (unverified inputs)','text':json.dumps(case,ensure_ascii=False)},
                             'assumption':{'label':'Unverified assumption','text':'Forecasts and judgments are not independently verified.'}})
        self.calculations=snapshots(case['finance']); self._calc_sources()
        self.history=[]; self.audit=[]; self.notes=[]; self.frames=None; self.memo=None
        self.status='idle'; self.stage='Ready'; self.round=0; self.nodes={}
        self.waiting=None; self.feedback=None; self.step_mode=False; self.permits=0
        self.stop_event=threading.Event(); self.lock=threading.RLock(); self.condition=threading.Condition(self.lock)
        self.thread=None; self.last_seen=time.monotonic()
    def _calc_sources(self):
        for key,value in [('calc:base',self.calculations['base']),('calc:downside',self.calculations['downside_25pct_revenue_drop'])]:
            self.sources[key]={'label':key+' (calculated from assumptions)','text':json.dumps(value)}
    def touch(self): self.last_seen=time.monotonic()
    def start(self,step=False):
        self.step_mode=step; self.permits=1 if step else 0
        self.thread=threading.Thread(target=self._run,daemon=True,name='boardroom-session'); self.thread.start()
    def _event(self,kind,**data):
        with self.lock: self.audit.append({'time':datetime.now(timezone.utc).isoformat(),'kind':kind,**data})
    def stop(self):
        self.stop_event.set()
        with self.condition: self.condition.notify_all()
    def pause(self):
        with self.condition: self.step_mode=True; self.permits=0
    def resume(self):
        with self.condition: self.step_mode=False; self.condition.notify_all()
    def step(self):
        with self.condition: self.step_mode=True; self.permits+=1; self.condition.notify_all()
    def answer(self,payload):
        with self.condition:
            if not self.waiting: return
            self.feedback=copy.deepcopy(payload); self.condition.notify_all()
    def _check(self):
        if self.stop_event.is_set(): raise Cancelled()
        if time.monotonic()-self.last_seen > 900:
            self.stop_event.set(); raise Cancelled()
    def _gate(self):
        with self.condition:
            while self.step_mode and self.permits<=0:
                self.status='paused'; self._check(); self.condition.wait(.2)
            self._check()
            if self.step_mode: self.permits-=1
            self.status='running'
    def _checkpoint(self,kind):
        with self.condition:
            self.waiting=kind; self.feedback=None; self.status='human_review'
            self._event('checkpoint',checkpoint=kind,round=self.round)
            while self.feedback is None:
                self._check(); self.condition.wait(.2)
            result=self.feedback; self.feedback=None; self.waiting=None; self.status='running'
        self._event('human_response',checkpoint=kind,response=result)
        return result
    def context(self):
        with self.lock:
            return copy.deepcopy({'case':self.case,'sources':self.sources,'calculations':self.calculations,
                                  'history':[{'role':h['role'],'round':h['round'],'phase':h['phase'],'output':h['output']} for h in self.history],'human_notes':self.notes,'round':self.round})
    def _agent(self,role,phase,context):
        self._check()
        with self.lock:
            self.nodes[role]={'status':'thinking','input':f'{phase} · round {self.round}; brief, evidence, calculations and prior completed round', 'output':'', 'phase':phase}
        self._event('agent_started',role=role,phase=phase,round=self.round)
        text=prompt(role,phase,context)
        for attempt in range(3):
            try:
                raw=self.provider.call(text,role,phase,self.stop_event,context)
                self._check()
                out=validate_output(raw,role,phase,self.sources)
                with self.lock:
                    self.nodes[role].update(status='done',output=out['summary']['text'],data=out)
                self._event('agent_done',role=role,phase=phase,round=self.round,attempt=attempt+1)
                return {'role':role,'phase':phase,'round':self.round,'output':out,'input':{'case':context['case'],'source_ids':list(context['sources']),'prior_messages':context['history'],'calculations':context['calculations'],'human_notes':context['human_notes']}}
            except (Cancelled,ProviderError):
                raise
            except (ValueError,TypeError,KeyError):
                self._event('malformed_output',role=role,phase=phase,attempt=attempt+1)
                text += '\nRETRY: Previous answer failed schema, source, role or word-limit validation. Return the complete corrected JSON. Use exactly the allowed IDs and requested role/phase.'
        raise ProviderError('The agent returned invalid structured output three times. Check the schema and source IDs, then start a new run.')
    def _batch(self,roles,phase):
        self._gate()
        with self.lock: self.stage=phase
        context=self.context()  # same immutable prior-round snapshot for every parallel agent
        graph=StateGraph(BatchState)
        def make_node(role):
            def run(state):
                try: return {'results':[self._agent(role,phase,context)]}
                except Exception as exc:
                    self.stop_event.set()
                    message=str(exc) if isinstance(exc,ProviderError) else 'Stopped.' if isinstance(exc,Cancelled) else 'Agent failed. Check input sizes and provider configuration.'
                    with self.lock: self.nodes[role]={'status':'failed','phase':phase,'input':phase,'output':message}
                    self._event('agent_failed',role=role,phase=phase,message=message)
                    raise
            return run
        for role in roles:
            graph.add_node(role,make_node(role)); graph.add_edge(START,role); graph.add_edge(role,END)
        result=graph.compile().invoke({'results':[]})['results']
        order={r:i for i,r in enumerate(roles)}
        result.sort(key=lambda v:order[v['role']])
        with self.lock: self.history.extend(result)
        return result
    def _run(self):
        try:
            self.status='running'
            framed=self._batch(['Moderator'],'frame')[0]['output']; self.frames=framed
            answer=self._checkpoint('frame')
            with self.lock:
                self.case['question']=answer.get('question',framed['summary']['text'])
                self.case['options']=answer.get('options',framed['options'])
                self.sources['confirmed_frame']={'label':'Human-confirmed frame','text':json.dumps(answer)}
            if self.case['researcher']: self._batch(['Researcher'],'research')
            for r in range(1,self.case['rounds']+1):
                self.round=r
                self._batch(self.case['agents'],'opening' if r==1 else 'rebuttal')
                answer=self._checkpoint('debate')
                if answer.get('challenge'):
                    with self.lock:
                        self.notes.append(answer['challenge'])
                        self.sources[f'human:{r}']={'label':f'Human challenge after round {r}','text':answer['challenge']}
                if answer.get('finance'):
                    revised=snapshots(answer['finance'])
                    with self.lock:
                        self.case['finance']=answer['finance']; self.calculations=revised; self._calc_sources()
                if answer.get('finish'): break
            self.memo=self._batch(['Moderator'],'synthesis')[0]['output']
            final_review=self._checkpoint('final')
            self.sources['human_final']={'label':'Final human board review','text':json.dumps(final_review)}
            self.status='complete'; self.stage='Board review recorded'
        except Cancelled:
            self.status='stopped'; self.stage='Stopped'
        except Exception as exc:
            self.status='failed'; self.stage=str(exc) if isinstance(exc,ProviderError) else 'Run failed. Review the failing agent and configuration.'
            self._event('run_failed',message=self.stage)
        finally:
            self.provider.clear()
    def scorecard(self):
        latest={}
        for h in self.history:
            if h['role'] in ROLES:
                o=h['output']; latest[h['role']]={'Agent':h['role'],'Stance':o['stance'],'Score':o['score'],'Confidence':o['confidence']}
        return list(latest.values())
    def snapshot(self):
        with self.lock:
            return copy.deepcopy(dict(status=self.status,stage=self.stage,round=self.round,nodes=self.nodes,history=self.history,
                waiting=self.waiting,frames=self.frames,memo=self.memo,case=self.case,calculations=self.calculations,notes=self.notes))
    def export(self):
        with self.lock:
            # Explicit allowlist: provider objects, API keys and environment never enter this payload.
            return copy.deepcopy({'schema_version':'1.0','mode':self.provider.kind,'model':self.provider.model,
                'case':self.case,'sources':self.sources,'calculations':self.calculations,'transcript':self.history,
                'events':self.audit,'scorecard':self.scorecard(),'memo':self.memo,'status':self.status,
                'usage':self.provider.meter.snapshot()})
