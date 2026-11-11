import html
import textwrap

def canvas(snapshot):
    nodes=snapshot['nodes']; active=snapshot['case']['agents']
    positions={'Moderator':(270,15),'Researcher':(270,135),'CEO':(35,265),'CFO':(500,265),'CMO':(35,405),'Risk Officer':(500,405),'Final memo':(270,550)}
    edges=[('Moderator','Researcher'),('Researcher','CEO'),('Researcher','CFO'),('Researcher','CMO'),('Researcher','Risk Officer'),('CEO','Final memo'),('CFO','Final memo'),('CMO','Final memo'),('Risk Officer','Final memo')]
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 675" role="img" aria-label="Live boardroom workflow"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#71859d"/></marker></defs><style>.flow{stroke-dasharray:7 5;animation:dash 1s linear infinite}@keyframes dash{to{stroke-dashoffset:-24}}</style>']
    for a,b in edges:
        x,y=positions[a]; xx,yy=positions[b]
        on=(nodes.get(b,{}).get('status')=='thinking' or (b=='Final memo' and snapshot['stage']=='synthesis'))
        svg.append(f'<path d="M{x+117},{y+102} L{xx+117},{yy}" fill="none" stroke="{"#33b6a0" if on else "#34445b"}" stroke-width="2" marker-end="url(#arrow)" class="{"flow" if on else ""}"/>')
    for role,(x,y) in positions.items():
        if role=='Final memo':
            node=nodes.get('Moderator',{}) if snapshot['stage']=='synthesis' or snapshot['memo'] else {}
        else: node=nodes.get(role,{})
        disabled=(role in ('CEO','CFO','CMO','Risk Officer') and role not in active) or (role=='Researcher' and not snapshot['case']['researcher'])
        status='off' if disabled else node.get('status','idle')
        color={'thinking':'#33b6a0','done':'#77a9f5','failed':'#fb8d8d','off':'#526073','idle':'#71859d'}[status]
        svg.append(f'<rect x="{x}" y="{y}" width="234" height="104" rx="9" fill="#172338" stroke="{color}" stroke-width="2"/>')
        title=html.escape(role+' · '+status)
        svg.append(f'<text x="{x+12}" y="{y+23}" fill="{color}" font-family="sans-serif" font-size="15" font-weight="bold">{title}</text>')
        lines=['IN: '+node.get('input','Awaiting prior stage'), 'OUT: '+node.get('output','—')]
        ypos=y+43
        for line in lines:
            for chunk in textwrap.wrap(line,33)[:2]:
                svg.append(f'<text x="{x+12}" y="{ypos}" fill="#d4dfef" font-family="sans-serif" font-size="11">{html.escape(chunk)}</text>'); ypos+=14
    svg.append('</svg>')
    return ''.join(svg)
