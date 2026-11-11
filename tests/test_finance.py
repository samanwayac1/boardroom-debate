import pytest
from boardroom.finance import calculate, snapshots

def test_npv_and_fractional_payback():
    r=calculate(100,[100,100],1,0,.1)
    assert r['npv_lakh']==73.55
    assert r['payback_years']==1
    assert r['annual_operating_break_even_revenue_lakh']==0

def test_break_even_and_unrecovered_investment():
    r=calculate(100,[100,100],.2,50,.1)
    assert r['payback_years'] is None
    assert r['annual_operating_break_even_revenue_lakh']==250
    assert calculate(0,[1],0,0,0)['payback_years']==0
    assert calculate(10,[1],0,0,0)['annual_operating_break_even_revenue_lakh'] is None

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-5])
def test_invalid_investment(bad):
    with pytest.raises(ValueError): calculate(bad,[1],.2,0,.1)

def test_downside_is_worse():
    s=snapshots(dict(investment=100,revenues=[100,200],margin=.5,fixed_cost=10,discount=.1))
    assert s['downside_25pct_revenue_drop']['npv_lakh']<s['base']['npv_lakh']
