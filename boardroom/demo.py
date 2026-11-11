"""Fixed offline responses. Never imports an SDK or accesses a network."""
def claim(text, source='assumption'): return {'text': text, 'source': source}

def response(role, phase, context):
    case = context['case']
    viewpoints = {
        'CEO': ('Conditional', 8, ['A staged entry could extend the brand beyond current urban markets.', 'A three-city pilot preserves strategic flexibility.', 'Scale should depend on repeat purchases and service performance.']),
        'CFO': ('Conditional', 6, ['Evaluate the supplied base NPV alongside the revenue downside.', 'Release capital in milestones rather than funding a national launch.', 'The forecast excludes tax and working capital; a full investment appraisal is still needed.']),
        'CMO': ('Support', 8, ['A pilot can test local channel economics and product-market fit.', 'Use city-specific pricing and distributor trials.', 'Validate demand with paid orders before scaling marketing spend.']),
        'Risk Officer': ('Oppose', 4, ['Demand forecasts have not been independently validated.', 'Service coverage and distributor credit could constrain execution.', 'Delay full rollout until downside liquidity and warranty capacity are tested.']),
    }
    stance, score, ideas = viewpoints.get(role, ('Neutral', 6, ['Compare the available options fairly.', 'Make assumptions visible.', 'Retain minority views.']))
    out = dict(role=role, phase=phase, stance=stance, score=score, confidence=6,
        summary=claim('CANNED DEMO: prefer a gated pilot, subject to evidence and downside controls.'),
        arguments=[claim(i) for i in ideas], key_assumption=claim('Pilot results may be informative for subsequent city launches.'),
        rebuttal=claim('Not applicable'), facts=[], options=[], recommendation='Not yet assessed', risks=[], dissent=[], conditions=[])
    if phase == 'frame': out.update(summary=claim(case['question'], 'brief'), options=case['options'])
    if phase == 'research':
        out['facts']=[claim('This case is fictional; forecasts are unverified teaching inputs.', 'brief'), claim('Base-case NPV is INR %.2f lakh.' % context['calculations']['base']['npv_lakh'], 'calc:base')]
    if phase == 'rebuttal':
        out['rebuttal']=claim('CANNED DEMO: other functions favor a pilot, but Risk remains opposed. Require a distributor trial, explicit loss limit and service-readiness review. Human challenges are recorded, but offline responses are fixed and do not reason about new inputs.')
    if phase == 'synthesis':
        risks=[('Demand falls below forecast', 'Gate scale-up on paid-order evidence'), ('Distributor credit losses', 'Set exposure limits and collection triggers'), ('Warranty and service overload', 'Audit local service capacity'), ('Cash flow shortfall', 'Maintain a cash buffer and stage capital release'), ('Premature nationwide expansion', 'Require a board review after the pilot')]
        out.update(stance='Conditional', recommendation='Conditional-go', risks=[{'risk': claim(a), 'mitigation': claim(b)} for a,b in risks],
                   dissent=[claim('Risk Officer opposes full rollout due to unvalidated demand and execution risk.')] if 'Risk Officer' in case['agents'] else [],
                   conditions=[claim('Approve only a three-city pilot; validate full financials and return to the board before scale-up.'),claim('Assign accountable owners, decision dates and measurable exit criteria before deployment.')])
        if context.get('human_notes'): out['conditions'].append(claim('Review the human challenge in the audit trail; canned demo text does not resolve it.'))
    return out
