from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile
MAX_FILE = 10 * 1024 * 1024
MAX_TEXT = 70000

def extract(name, data, prefix):
    """Parse locally; never execute formulas, macros or embedded objects."""
    if len(data) > MAX_FILE: raise ValueError('Each file must be at most 10 MB.')
    ext = Path(name).suffix.lower()
    parts = []
    if ext == '.txt': parts = [(prefix + ':text', data.decode('utf-8-sig'))]
    elif ext in ('.pdf', '.xlsx'):
        if ext == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted: raise ValueError('Use an unencrypted PDF.')
            if len(reader.pages) > 200: raise ValueError('Limit PDFs to 200 pages.')
            parts = [(f'{prefix}:p{i+1}', p.extract_text() or '') for i,p in enumerate(reader.pages)]
        else:
            from openpyxl import load_workbook
            try:
                with ZipFile(BytesIO(data)) as z:
                    if sum(x.file_size for x in z.infolist()) > 80 * 1024 * 1024:
                        raise ValueError('Workbook expands beyond the 80 MB limit.')
            except BadZipFile: raise ValueError('Invalid XLSX file.')
            w = load_workbook(BytesIO(data), read_only=True, data_only=True, keep_links=False)
            try:
                for si, s in enumerate(w):
                    if si >= 20: raise ValueError('Limit workbooks to 20 sheets.')
                    if s.max_column and s.max_column>40: raise ValueError('Limit workbooks to 40 columns per sheet.')
                    rows=[]
                    for ri, row in enumerate(s.iter_rows(values_only=True)):
                        if ri >= 5000: raise ValueError('Limit each sheet to 5,000 rows.')
                        rows.append(' | '.join(str(v) if v is not None else '' for v in row[:40]))
                        if sum(map(len,rows)) > MAX_TEXT: raise ValueError('Workbook text is too large.')
                    parts.append((f'{prefix}:sheet{si+1}', s.title + '\n' + '\n'.join(rows)))
            finally: w.close()
    else: raise ValueError('Supported files: PDF, TXT, XLSX.')
    if sum(len(t) for _,t in parts) > MAX_TEXT: raise ValueError('Extracted text exceeds 70,000 characters; upload a shorter excerpt.')
    result = {k: {'label': f'{name} / {k.split(":")[-1]}', 'text': t} for k,t in parts if t.strip()}
    if not result: raise ValueError('No readable text found. For scanned PDFs, run OCR first.')
    return result
