import math

def calculate(investment, revenues, margin, fixed_cost, discount):
    """Amounts in INR lakh. Unlevered simplified cash flows, no terminal value."""
    values = [investment, margin, fixed_cost, discount, *revenues]
    if not revenues or not all(math.isfinite(float(x)) for x in values):
        raise ValueError('Enter finite financial values and at least one forecast year.')
    if investment < 0 or fixed_cost < 0 or any(x < 0 for x in revenues):
        raise ValueError('Investment, fixed cost and revenue cannot be negative.')
    if not 0 <= margin <= 1 or discount <= -1:
        raise ValueError('Margin must be 0–100%; discount must exceed -100%.')
    cash = [r * margin - fixed_cost for r in revenues]
    npv = -investment + sum(c / (1 + discount) ** (i + 1) for i, c in enumerate(cash))
    cumulative = -investment
    payback = 0.0 if investment == 0 else None
    for i, c in enumerate(cash):
        previous = cumulative
        cumulative += c
        if payback is None and previous < 0 <= cumulative and c > 0:
            payback = i + (-previous / c)
    return {'investment_lakh': investment, 'revenues_lakh': revenues,
            'margin': margin, 'fixed_cost_lakh': fixed_cost, 'discount_rate': discount,
            'cash_flows_lakh': cash, 'npv_lakh': round(npv, 2),
            'payback_years': None if payback is None else round(payback, 2),
            'annual_operating_break_even_revenue_lakh': None if margin == 0 else round(fixed_cost / margin, 2),
            'method': 'Year-end cash flows = revenue × contribution margin − annual fixed operating cost. Initial capex at t=0. No tax, working capital, residual value or financing cash flows.'}

def snapshots(finance):
    return {'base': calculate(**finance), 'downside_25pct_revenue_drop': calculate(**{**finance, 'revenues': [r * .75 for r in finance['revenues']]})}
