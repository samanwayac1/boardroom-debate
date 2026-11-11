import json
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from boardroom.canvas import canvas
from boardroom.engine import Runner
from boardroom.exports import markdown, docx_bytes, pdf_bytes
from boardroom.finance import snapshots
from boardroom.inputs import extract
from boardroom.models import ROLES
from boardroom.providers import Provider, Meter

ROOT=Path(__file__).parent
LOCAL=os.getenv('BOARDROOM_LOCAL')=='1'
if LOCAL: load_dotenv(ROOT/'.env',override=False)
SAMPLE=json.loads((ROOT/'data/sample_case.json').read_text())
st.set_page_config(page_title='Board-Room Debate',page_icon='◈',layout='wide')
st.markdown('<style>.block-container{padding-top:2rem}div[data-testid="stMetric"]{background:#172338;padding:14px;border-radius:10px}h1{letter-spacing:-1px}</style>',unsafe_allow_html=True)
st.caption('STRATEGY WORKSPACE  /  HUMAN-LED DECISIONS')
st.title('Board-Room Debate')
st.write('Bring independent leadership views into one decision. Examine the evidence, challenge assumptions, and keep dissent visible.')
runner=st.session_state.get('runner')
busy=runner is not None and runner.status not in ('complete','failed','stopped')

with st.sidebar:
    st.subheader('Connection')
    choice=st.selectbox('Use your own provider',['ChatGPT subscription','OpenAI API','Anthropic API'],disabled=busy)
    kind={'ChatGPT subscription':'chatgpt','OpenAI API':'openai','Anthropic API':'anthropic'}[choice]
    key=''; model=''; local_cli=False
    if kind=='chatgpt':
        modes=['Copy and paste with ChatGPT']+(['Local Codex CLI'] if LOCAL else [])
        local_cli=st.selectbox('Subscription connection',modes,disabled=busy)=='Local Codex CLI'
        if local_cli:
            model=st.text_input('Codex model (blank uses your account default)',disabled=busy)
            st.caption('Requires a recent Codex CLI and your dedicated ChatGPT login. See README. Uses plan limits; no API fallback.')
        else:
            st.info('Works on Streamlit Cloud: copy each agent prompt into your own ChatGPT chat, then paste its JSON response here. This mode requires manual handoffs.')
            st.link_button('Open ChatGPT','https://chatgpt.com/')
    else:
        models=['gpt-4.1-mini','gpt-4.1','Custom model ID'] if kind=='openai' else ['claude-sonnet-4-5','claude-haiku-4-5','Custom model ID']
        model=st.selectbox('Model',models,disabled=busy)
        if model=='Custom model ID': model=st.text_input('Exact model ID',disabled=busy)
        key=st.text_input('Your API key',type='password',key='api_key_'+kind,disabled=busy)
        if LOCAL: key=key or os.getenv('OPENAI_API_KEY' if kind=='openai' else 'ANTHROPIC_API_KEY','')
        st.caption('Each visitor supplies their own key. API usage is separate from ChatGPT subscription usage. Model access depends on your account.')
    with st.expander('API cost guard'):
        st.caption('Editable USD rates per million tokens. Examples only; confirm your selected model’s current rates. The cap uses these rates, excludes tax, and is not a provider billing limit.')
        ir=st.number_input('Input rate USD / 1M tokens',min_value=.001,value=.4,format='%.3f',disabled=busy)
        out_rate=st.number_input('Output rate USD / 1M tokens',min_value=.001,value=1.6,format='%.3f',disabled=busy)
        cap=st.number_input('Run cost cap USD',min_value=.01,value=1.0,disabled=busy)
    st.divider()
    if st.button('▶ Demo Run',disabled=busy,width='stretch'):
        r=Runner(SAMPLE,{},Provider('demo')); st.session_state.runner=r; r.start(); st.rerun()
    st.caption('Fixed fictional case. No key, login or internet needed after dependencies are installed.')
    if st.button('Clear session',disabled=busy,width='stretch'):
        if runner: runner.stop(); runner.provider.clear()
        st.session_state.clear(); st.rerun()
    st.caption('Web search is off. Research uses only your supplied evidence. No telemetry or external tracing is added by this app.')

with st.expander('Decision brief and run settings',expanded=runner is None):
    with st.form('setup'):
        question=st.text_area('Decision question',SAMPLE['question'],max_chars=2000)
        a,b=st.columns(2)
        company=a.text_input('Company',SAMPLE['company'],max_chars=200)
        sector=b.text_input('Sector',SAMPLE['sector'],max_chars=200)
        budget=a.number_input('Available budget (INR lakh)',min_value=0.0,value=500.0)
        horizon=b.text_input('Decision horizon','5 years',max_chars=100)
        options=st.text_area('Options — one per line','\n'.join(SAMPLE['options']),max_chars=2000)
        constraints=st.text_area('Company context and constraints',SAMPLE['constraints'],max_chars=12000)
        c1,c2,c3=st.columns(3)
        rounds=c1.slider('Total debate rounds',1,3,2)
        appetite=c2.selectbox('Risk appetite',['Low','Medium','High'],index=1)
        researcher=c3.checkbox('Include Researcher',True)
        agents=st.multiselect('Functional agents',ROLES,default=ROLES)
        st.caption('Round 1 = independent opening positions. Later rounds = rebuttals based on the previous completed round. Pause/Step operates on a stage or a parallel round.')
        st.markdown('**Financial assumptions · INR lakh**')
        f1,f2,f3,f4=st.columns(4)
        inv=f1.number_input('Initial investment',min_value=0.0,value=300.0)
        margin=f2.number_input('Contribution margin %',min_value=0.0,max_value=100.0,value=32.0)
        fixed=f3.number_input('Annual fixed operating cost',min_value=0.0,value=90.0)
        discount=f4.number_input('Discount rate %',min_value=0.0,max_value=100.0,value=12.0)
        revenue=st.text_input('Annual revenue forecast — comma-separated','300,500,750,950,1100',max_chars=1000)
        st.caption('Cash flow = revenue × contribution margin − fixed costs. No tax, working capital, terminal value or financing. A 25% revenue downside is calculated separately.')
        files=st.file_uploader('Supporting evidence · PDF, TXT or XLSX · up to 10 MB each',type=['pdf','txt','xlsx'],accept_multiple_files=True)
        step=st.checkbox('Start in step-through mode',False)
        consent=st.checkbox('Send the brief and extracted evidence to my selected provider for this run. For ChatGPT handoffs, I will send the prompts myself.')
        submitted=st.form_submit_button('Start boardroom debate',disabled=busy)
    if submitted:
        try:
            if not question.strip(): raise ValueError('Enter a decision question.')
            if not agents: raise ValueError('Select at least one functional agent.')
            if not consent: raise ValueError('Confirm the selected-provider data use to start.')
            if kind!='chatgpt' and (not key or not model.strip()): raise ValueError('Enter your own API key and a model ID.')
            revenues=[float(x.strip()) for x in revenue.split(',')]
            if len(revenues)>10: raise ValueError('Use at most ten forecast years.')
            fin=dict(investment=inv,revenues=revenues,margin=margin/100,fixed_cost=fixed,discount=discount/100)
            snapshots(fin)
            if inv>budget: st.warning('The investment exceeds your stated budget. The board will see this constraint.')
            sources={}
            if len(files)>5: raise ValueError('Upload at most five evidence files.')
            for i,f in enumerate(files): sources.update(extract(f.name,f.getvalue(),f'file:{i+1}'))
            if sum(len(s['text']) for s in sources.values())>100000: raise ValueError('Combined evidence exceeds 100,000 characters. Use shorter excerpts.')
            case=dict(question=question.strip(),options=[x.strip() for x in options.splitlines() if x.strip()] or ['Proceed','Pilot','Do not proceed'],company=company,sector=sector,budget_lakh=budget,
                      constraints=constraints,horizon=horizon,risk_appetite=appetite,rounds=rounds,agents=agents,researcher=researcher,finance=fin,note='User-supplied inputs and forecasts; not independently verified.')
            if len(case['options'])>8: raise ValueError('Use at most eight options.')
            p=Provider(kind,model,key,Meter(ir,out_rate,cap),local_cli=local_cli)
            r=Runner(case,sources,p); st.session_state.runner=r; r.start(step); st.rerun()
        except (ValueError,UnicodeError):
            # Parser/input errors have no API credentials. Show a concise local validation message.
            import sys
            st.error(str(sys.exc_info()[1])[:300])
        except Exception:
            st.error('Could not parse the inputs. Check that files are readable and financial fields contain numbers.')


def checkpoint(r,s):
    kind=s['waiting']
    if kind=='frame':
        st.info('Review 1 of 3 · Confirm the decision and options before research and functional agents run.')
        with st.form('frame_review'):
            q=st.text_area('Framed decision',s['frames']['summary']['text'],max_chars=2000)
            opts=st.text_area('Confirmed options','\n'.join(s['frames']['options']),max_chars=2000)
            if st.form_submit_button('Confirm framing'):
                arr=[x.strip() for x in opts.splitlines() if x.strip()]
                if q.strip() and 1<=len(arr)<=8: r.answer({'question':q.strip(),'options':arr}); st.rerun()
                else: st.error('Enter a question and between one and eight options.')
    elif kind=='debate':
        last=s['round']>=s['case']['rounds']
        st.info(f"Review 2 of 3 · Round {s['round']} complete. "+('The Moderator will address your challenge in the memo; the round cap has been reached.' if last else 'Challenge the panel or revise assumptions before the next round.'))
        with st.form('debate_review_'+str(s['round'])):
            challenge=st.text_area('Challenge question or feedback (optional)',max_chars=4000)
            revise=st.checkbox('Revise financial assumptions')
            current=s['case']['finance']
            col1,col2=st.columns(2)
            new_inv=col1.number_input('Revised investment (INR lakh)',min_value=0.0,value=float(current['investment']))
            new_margin=col2.number_input('Revised contribution margin %',min_value=0.0,max_value=100.0,value=float(current['margin']*100))
            new_fixed=col1.number_input('Revised fixed cost (INR lakh)',min_value=0.0,value=float(current['fixed_cost']))
            new_rate=col2.number_input('Revised discount rate %',min_value=0.0,max_value=100.0,value=float(current['discount']*100))
            new_rev=st.text_input('Revised annual revenue forecast',','.join(str(x) for x in current['revenues']),max_chars=1000)
            finish=st.checkbox('End debate early and ask Moderator to synthesise',value=last,disabled=last)
            if st.form_submit_button('Continue to memo' if last else 'Apply feedback and continue'):
                try:
                    payload={'challenge':challenge,'finish':finish}
                    if revise:
                        fin=dict(investment=new_inv,revenues=[float(x.strip()) for x in new_rev.split(',')],margin=new_margin/100,fixed_cost=new_fixed,discount=new_rate/100)
                        if len(fin['revenues'])>10: raise ValueError('Use at most ten forecast years.')
                        snapshots(fin); payload['finance']=fin
                    r.answer(payload); st.rerun()
                except ValueError: st.error('Check revised financial numbers and the forecast length.')
    elif kind=='final':
        st.info('Review 3 of 3 · Accept, edit or reject the recommendation. Your disposition is recorded separately from the agent output.')
        with st.form('final_review'):
            disposition=st.selectbox('Human disposition',['Accept','Edit / override','Reject'])
            recommendation=st.selectbox('Board decision',['Go','No-go','Conditional-go','Defer'],index=['Go','No-go','Conditional-go'].index(s['memo']['recommendation']))
            summary=st.text_area('Editable board summary',s['memo']['summary']['text'],max_chars=600)
            note=st.text_area('Decision note / owner / next review date',max_chars=600)
            if st.form_submit_button('Record board decision'):
                r.answer(dict(disposition=disposition,recommendation=recommendation,summary=summary,note=note)); st.rerun()

@st.fragment(run_every='1s')
def room():
    r=st.session_state.get('runner')
    if r is None:
        st.info('Try Demo Run, or enter a brief to start your own debate.'); return
    r.touch(); s=r.snapshot()
    st.divider(); st.subheader('Debate room')
    if r.provider.kind=='demo': st.warning('CANNED OFFLINE DEMO · fixed responses for the fictional sample case · no live AI reasoning')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Status',s['status'].replace('_',' ').title()); c2.metric('Round',str(s['round'])+' / '+str(s['case']['rounds']))
    usage=r.provider.meter.snapshot()
    api=r.provider.kind in ('openai','anthropic')
    c3.metric('Tokens'+(' (estimate)' if usage['estimated_usage'] else ''),f"{usage['input_tokens']+usage['output_tokens']:,}" if api else 'Not metered')
    c4.metric('Estimated API cost',f"${usage['estimated_cost_usd']:.4f}" if api else '$0 API calls')
    st.caption(s['stage']+(' · Subscription limits apply; ChatGPT/Codex usage is not estimated as API dollars.' if r.provider.kind=='chatgpt' else ''))
    running=s['status'] not in ('complete','failed','stopped')
    a,b,c,d=st.columns(4)
    if a.button('Pause',disabled=not running): r.pause()
    if b.button('Resume',disabled=not running): r.resume()
    if c.button('Step',disabled=not running): r.step()
    if d.button('Stop',disabled=not running): r.stop()
    st.caption('Pause takes effect after the current stage; Step permits one stage (including a parallel round). Stop prevents new work and discards arriving responses. An API request already sent may still be billed.')
    if s['status']=='failed': st.error(s['stage'])
    left,right=st.columns([1.15,1])
    with left:
        st.markdown('**Workflow canvas**')
        st.image(canvas(s),width='stretch')
        with st.expander('Inspect current agent input and output'):
            names=['Moderator','Researcher']+ROLES
            selected=st.selectbox('Agent',names)
            st.json(s['nodes'].get(selected,{'status':'idle'}))
            entries=[h for h in s['history'] if h['role']==selected]
            if entries: st.json(entries[-1]['input'])
    with right:
        st.markdown('**Live transcript**')
        with st.container(height=540):
            for h in s['history']:
                o=h['output']
                with st.chat_message('assistant'):
                    st.markdown(f"**{h['role']}** · {h['phase']} · round {h['round']}")
                    st.write(o['summary']['text']+' ['+o['summary']['source']+']')
                    if h['role'] in ROLES: st.caption(f"{o['stance']} · score {o['score']}/10 · confidence {o['confidence']}/10")
                    with st.expander('Arguments and structured output'): st.json(o)
    pending=r.provider.handoffs()
    if pending:
        st.subheader('ChatGPT handoffs')
        st.write('For each request, copy the complete prompt into a separate chat in your own ChatGPT account. Ask it to return JSON only, then paste the response. The app validates it before continuing.')
        for request in pending:
            with st.expander(request['role']+' · '+request['phase'],expanded=True):
                st.code(request['prompt'],language='text',height=220)
                st.download_button('Download this prompt',request['prompt'],file_name=request['role'].replace(' ','_')+'_prompt.txt',key='dl_'+request['id'])
                with st.form('handoff_'+request['id']):
                    answer=st.text_area('Paste ChatGPT JSON response',height=180,key='response_'+request['id'])
                    if st.form_submit_button('Submit agent response'):
                        try: r.provider.submit(request['id'],answer); st.rerun()
                        except (ValueError,TypeError): st.error('Paste one valid JSON object. Remove any surrounding explanation.')
    if s['waiting']: checkpoint(r,s)
    if s['history']:
        st.markdown('**Scorecard · latest position per active agent**')
        st.dataframe(r.scorecard(),hide_index=True,width='stretch')
    st.markdown('**Financial snapshot · calculated from assumptions**')
    rows=[]
    for name,f in s['calculations'].items():
        rows.append({'Scenario':name,'NPV (INR lakh)':f['npv_lakh'],'Payback years':str(f['payback_years']) if f['payback_years'] is not None else 'Not reached','Annual break-even revenue (INR lakh)':f['annual_operating_break_even_revenue_lakh']})
    st.dataframe(rows,hide_index=True,width='stretch')
    payload=r.export()
    if s['memo']:
        st.markdown(markdown(payload))
        st.caption('Documents are concise briefs; long claims may be shortened. JSON retains full content. For Indian-language text use DOCX; PDF uses standard Latin fonts.')
        # Build only when the memo or final review changes, not on every timer tick.
        memo_signature=json.dumps({'memo':payload['memo'],'events':[e for e in payload['events'] if e.get('checkpoint')=='final'],'calculations':payload['calculations']},sort_keys=True)
        if st.session_state.get('memo_signature')!=memo_signature:
            st.session_state.memo_signature=memo_signature
            st.session_state.docx=docx_bytes(payload); st.session_state.pdf=pdf_bytes(payload)
        e1,e2,e3=st.columns(3)
        e1.download_button('Board memo · DOCX',st.session_state.docx,'board_memo.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        e2.download_button('Board memo · PDF',st.session_state.pdf,'board_memo.pdf','application/pdf')
        e3.download_button('Board memo · Markdown',markdown(payload),'board_memo.md','text/markdown')
    st.download_button('Full transcript, evidence and audit trail · JSON',json.dumps(payload,ensure_ascii=False,indent=2),'boardroom_transcript.json','application/json')
    st.caption('Transcript exports include company evidence and human inputs. API keys and login credentials are excluded. Session state is temporary; download your work before clearing or closing.')
    if r.status in ('complete','failed','stopped') and busy: st.rerun()

room()
