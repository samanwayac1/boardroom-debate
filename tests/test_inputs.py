from io import BytesIO
import pytest
from openpyxl import Workbook
from boardroom.inputs import extract

def test_txt_sources_and_size_limit():
    assert extract('note.txt',b'Forecast not audited','file:1')['file:1:text']['text']=='Forecast not audited'
    with pytest.raises(ValueError): extract('a.txt',b'x'*(10*1024*1024+1),'file:1')

def test_workbook_reads_values_not_formulas():
    w=Workbook(); w.active.append(['Revenue',100]); w.active.append(['Formula','=1+1'])
    b=BytesIO(); w.save(b)
    text=extract('a.xlsx',b.getvalue(),'file:1')['file:1:sheet1']['text']
    assert 'Revenue | 100' in text
    assert '=1+1' not in text

def test_rejects_bad_and_empty_files():
    with pytest.raises(ValueError): extract('a.xlsx',b'invalid','file:1')
    with pytest.raises(ValueError): extract('a.txt',b'  ','file:1')
