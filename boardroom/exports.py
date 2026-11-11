from io import BytesIO
from xml.sax.saxutils import escape

def tagged(c): return c['text'] + ' [' + c['source'] + ']'
def short(text,limit=230): return text if len(text)<=limit else text[:limit-1].rsplit(' ',1)[0]+'…'
def human_decision(payload):
    entries=[e['response'] for e in payload['events'] if e['kind']=='human_response' and e.get('checkpoint')=='final']
    return entries[-1] if entries else None

def sections(payload):
    memo=payload['memo']
    if not memo: return [('Board memo','No memo generated yet.')]
    decision=human_decision(payload)
    opening=f"AI recommendation: {memo['recommendation']} · confidence {memo['confidence']}/10 (subjective).\n"+tagged(memo['summary'])
    if decision:
        opening+='\nHuman disposition: '+decision['disposition']+' · Board decision: '+decision['recommendation']+' [human_final]'
        if decision.get('summary'): opening+='\nHuman-edited summary: '+decision['summary']+' [human_final]'
        if decision.get('note'): opening+='\nHuman note: '+decision['note']+' [human_final]'
    result=[('Decision',opening)]
    latest={h['role']:h['output'] for h in payload['transcript'] if h['role'] in payload['case']['agents']}
    result.append(('Views by function','\n'.join(f"{role} — {o['stance']} ({o['score']}/10): "+short(tagged(o['arguments'][0]),240) for role,o in latest.items())))
    result.append(('Dissent','\n'.join(tagged(c) for c in memo['dissent']) or 'No dissent was recorded by the Moderator [assumption]. See individual positions.'))
    result.append(('Key risks and mitigations','\n'.join(f"{i+1}. {tagged(r['risk'])} → {tagged(r['mitigation'])}" for i,r in enumerate(memo['risks']))))
    result.append(('Conditions and next steps','\n'.join(tagged(c) for c in memo['conditions'])))
    return result

def markdown(payload):
    text='# Board decision memo\n\n'+('FINAL REVIEW RECORDED' if human_decision(payload) else 'DRAFT — awaiting final human review')+'\n\n'+payload['case']['question']+' [confirmed_frame]\n\n'
    if payload['mode']=='demo': text+='**CANNED OFFLINE DEMO · fictional case · no live AI reasoning**\n\n'
    for title,body in sections(payload): text+='## '+title+'\n\n'+body.replace('\n','\n\n')+'\n\n'
    text+='## Financial snapshot\n\n| Scenario | NPV (INR lakh) | Payback (years) | Annual operating break-even revenue (INR lakh) |\n|---|---:|---:|---:|\n'
    for key,s in payload['calculations'].items():
        source='calc:base' if key=='base' else 'calc:downside'
        text+=f"| {key} [{source}] | {s['npv_lakh']:,.2f} | {s['payback_years'] if s['payback_years'] is not None else 'Not reached'} | {s['annual_operating_break_even_revenue_lakh'] if s['annual_operating_break_even_revenue_lakh'] is not None else 'Undefined'} |\n"
    text+='\n'+payload['calculations']['base']['method']+' [calc:base]\n\nSource labels identify supplied evidence, not independent verification. Full arguments and input versions are in the transcript. The app advises; the board decides.\n'
    return text

def docx_bytes(payload):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    d=Document(); s=d.sections[0]
    s.page_width=Inches(8.5); s.page_height=Inches(11)
    s.top_margin=s.bottom_margin=Inches(.6); s.left_margin=s.right_margin=Inches(.65)
    for name in ('Normal','Title','Subtitle','Heading 1','Heading 2'):
        style=d.styles[name]; style.font.name='Calibri'; style.font.color.rgb=RGBColor(0,0,0)
    normal=d.styles['Normal']; normal.font.size=Pt(10); normal.paragraph_format.space_after=Pt(5)
    d.styles['Title'].font.size=Pt(21); d.styles['Heading 1'].font.size=Pt(13)
    d.add_heading('Board decision memo',0)
    d.add_paragraph('FINAL REVIEW RECORDED' if human_decision(payload) else 'DRAFT — awaiting final human review')
    d.add_paragraph(short(payload['case']['question'],240)+' [confirmed_frame]')
    d.add_paragraph('CANNED DEMO — fictional teaching case' if payload['mode']=='demo' else 'Advisory memo — human review required',style='Subtitle')
    parts=dict(sections(payload))
    for title in ('Decision','Views by function','Dissent'):
        d.add_heading(title,1)
        for line in parts[title].splitlines(): d.add_paragraph(short(line,300))
    d.add_heading('Financial snapshot in INR lakh',1)
    table=d.add_table(rows=1,cols=4); table.style='Light Shading Accent 1'
    for c,t in zip(table.rows[0].cells,['Scenario','NPV','Payback years','Break-even revenue']): c.text=t
    for key,calc in payload['calculations'].items():
        cells=table.add_row().cells
        vals=['Base [calc:base]' if key=='base' else 'Revenue −25% [calc:downside]',str(calc['npv_lakh']),str(calc['payback_years']) if calc['payback_years'] is not None else 'Not reached',str(calc['annual_operating_break_even_revenue_lakh']) if calc['annual_operating_break_even_revenue_lakh'] is not None else 'Undefined']
        for c,v in zip(cells,vals): c.text=v
    for row in table.rows:
        for cell in row.cells:
            tcpr=cell._tc.get_or_add_tcPr(); borders=OxmlElement('w:tcBorders')
            for edge in ('top','left','bottom','right'):
                el=OxmlElement('w:'+edge); el.set(qn('w:val'),'single'); el.set(qn('w:sz'),'4'); el.set(qn('w:color'),'D9D9D9'); borders.append(el)
            tcpr.append(borders)
    d.add_paragraph(short(payload['calculations']['base']['method'],430)+' [calc:base]')
    d.add_page_break(); d.add_heading('Risks and implementation conditions',0)
    for i,r in enumerate(payload['memo']['risks']):
        d.add_heading(str(i+1)+'. '+short(tagged(r['risk']),160),1)
        d.add_paragraph(short(tagged(r['mitigation']),230))
    d.add_heading('Conditions and next steps',1)
    for c in payload['memo']['conditions']: d.add_paragraph(short(tagged(c),180),style='List Bullet')
    d.add_heading('Evidence and interpretation',1)
    d.add_paragraph('Source IDs refer to the source registry in the JSON transcript. Source labels do not verify accuracy. Financial forecasts and judgments are assumptions. This two-page brief shortens long text; the full transcript is authoritative. The board decides.')
    d.add_paragraph('Active roles: '+', '.join(payload['case']['agents'])+'. Round cap: '+str(payload['case']['rounds'])+'.')
    for root in (d.styles.element, d.element):
        for border in list(root.xpath('.//w:pBdr')): border.getparent().remove(border)
    bio=BytesIO(); d.save(bio); return bio.getvalue()

def pdf_bytes(payload):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    buf=BytesIO(); styles=getSampleStyleSheet()
    styles['BodyText'].fontSize=9; styles['BodyText'].leading=12
    story=[]
    def para(t,style='BodyText'):
        # Built-in PDF fonts cover Latin; replace unsupported scripts predictably.
        t=t.replace('→',' to ').replace('−','-').replace('…','...').encode('cp1252','replace').decode('cp1252')
        story.append(Paragraph(escape(t),styles[style])); story.append(Spacer(1,5))
    para('Board decision memo','Title'); para(short(payload['case']['question'],240)+' [confirmed_frame]')
    if payload['mode']=='demo': para('CANNED DEMO - fictional teaching case')
    parts=dict(sections(payload))
    for title in ('Decision','Views by function','Dissent'):
        para(title,'Heading2')
        for line in parts[title].splitlines(): para(short(line,300))
    para('Financial snapshot in INR lakh','Heading2')
    data=[['Scenario','NPV','Payback years','Break-even revenue']]
    for key,c in payload['calculations'].items():
        data.append(['Base [calc:base]' if key=='base' else 'Revenue -25% [calc:downside]',str(c['npv_lakh']),str(c['payback_years']) if c['payback_years'] is not None else 'Not reached',str(c['annual_operating_break_even_revenue_lakh'])])
    table=Table(data,colWidths=[180,60,90,150]); table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.lightgrey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8EDF2')),('FONTSIZE',(0,0),(-1,-1),9),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(table); para(payload['calculations']['base']['method']+' [calc:base]')
    story.append(PageBreak()); para('Risks and implementation conditions','Title')
    for i,r in enumerate(payload['memo']['risks']):
        para(str(i+1)+'. '+short(tagged(r['risk']),160),'Heading2'); para(short(tagged(r['mitigation']),230))
    para('Conditions and next steps','Heading2')
    for c in payload['memo']['conditions']: para(short(tagged(c),180))
    para('Source IDs map to the JSON transcript. Financial forecasts and judgments are assumptions. The brief shortens long text; the full transcript is authoritative. The board decides.')
    SimpleDocTemplate(buf,pagesize=letter,topMargin=40,bottomMargin=40,leftMargin=42,rightMargin=42).build(story)
    return buf.getvalue()
