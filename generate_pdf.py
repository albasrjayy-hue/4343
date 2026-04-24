#!/usr/bin/env python3
"""
generate_pdf.py — Delivery Organizer
Reads Arabic delivery-report PDF, groups by store, sorts by address.
Generates output PDF via wkhtmltopdf for proper Arabic/RTL rendering.
"""

import sys, json, re, os, subprocess, tempfile, datetime

try:
    import pdfplumber
except ImportError:
    print("ERROR: pip install pdfplumber", file=sys.stderr); sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────
STORE_CODES = ['HD','AF','FLF','ML','SW','AB','SY','RB','SHB','NC','LF','NW','FLB','SHF']
DATE_RE     = re.compile(r'^\d{4}-\d{2}-\d{2}$')
AMOUNT_RE   = re.compile(r'^-?[\d,]+$')
PHONE_RE    = re.compile(r'^0[0-9]{9,}$')
RECEIPT_RE  = re.compile(r'^1[3-9]\d{4,6}$')

# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_store(t):
    for c in STORE_CODES:
        if re.search(r'\b' + c + r'\b', t): return c
    return None

def is_date(t):    return bool(DATE_RE.match(t.strip()))
def is_amount(t):  return bool(AMOUNT_RE.match(t.replace(',','').strip())) and len(t.strip()) >= 2
def is_phone(t):   return bool(PHONE_RE.match(t.replace(' ','').replace('-','')))
def is_receipt(t): return bool(RECEIPT_RE.match(t.strip()))

def h(text):
    """HTML-escape."""
    return (str(text)
        .replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        .replace('"','&quot;'))

# ── PDF Extraction ────────────────────────────────────────────────────────────
def extract_rows(pdf_path):
    records = []
    total_pages = 0
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                for row in table:
                    if not row: continue
                    cells = [str(c).strip() if c else '' for c in row]
                    rec = parse_row(cells)
                    if rec: records.append(rec)
    return records, total_pages

def parse_row(cells):
    non_empty = [c for c in cells if c.strip()]
    if len(non_empty) < 3: return None
    # Skip pure header rows
    date_count = sum(1 for c in non_empty if is_date(c))
    if date_count >= len(non_empty) - 1: return None

    store = notes = date = status = phone = address = receipt_no = ''
    amounts = []

    for c in cells:
        c = c.strip()
        if not c: continue
        s = extract_store(c)
        if s and not store:
            store = s
            notes = c; continue
        if is_date(c) and not date:
            date = c; continue
        if 'تم التسليم' in c:
            status = 'تم التسليم جزئياً' if 'جزئياً' in c else 'تم التسليم'
            continue
        if is_receipt(c) and not receipt_no:
            receipt_no = c; continue
        if is_phone(c) and not phone:
            phone = c; continue
        if is_amount(c):
            amounts.append(c); continue
        if len(c) > 2 and not is_date(c) and not is_amount(c):
            if not address: address = c
            else: address += ' ' + c

    if not store and not receipt_no: return None

    net   = amounts[0] if len(amounts) > 0 else ''
    fee   = amounts[1] if len(amounts) > 1 else ''
    total = amounts[2] if len(amounts) > 2 else ''

    return {
        'store': store or 'UNKNOWN',
        'receipt_no': receipt_no,
        'date': date,
        'status': status or 'تم التسليم',
        'net': net, 'fee': fee, 'total': total,
        'phone': phone,
        'address': address.strip(),
        'notes': notes,
    }

# ── Sorting ───────────────────────────────────────────────────────────────────
def sort_records(records):
    valid = [r for r in records if r['store'] != 'UNKNOWN']
    groups = {}
    for r in valid:
        groups.setdefault(r['store'], []).append(r)
    result = []
    for store in sorted(groups):
        grp = sorted(groups[store], key=lambda x: x['address'])
        result.extend(grp)
    return result, groups

# ── HTML Generation ───────────────────────────────────────────────────────────
def build_html(records, groups, total_pages):
    today = datetime.date.today().strftime('%Y-%m-%d')

    # Grand total
    grand_net = 0
    for r in records:
        try: grand_net += int(r['net'].replace(',',''))
        except: pass

    rows_html = []
    global_idx = 0
    for store in sorted(groups):
        store_rows = groups[store]
        store_net = 0
        for r in store_rows:
            try: store_net += int(r['net'].replace(',',''))
            except: pass

        rows_html.append(f'''
        <tr class="store-header">
          <td colspan="13">
            متجر: <strong>{h(store)}</strong>
            &nbsp;&nbsp;|&nbsp;&nbsp; عدد الطلبات: <strong>{len(store_rows)}</strong>
            &nbsp;&nbsp;|&nbsp;&nbsp; إجمالي الصافي: <strong>{store_net:,}</strong> د.ع
          </td>
        </tr>''')

        for i, r in enumerate(store_rows):
            global_idx += 1
            cls = 'even' if i % 2 == 0 else 'odd'
            notes_short = r['notes'][:35] + '…' if len(r['notes']) > 35 else r['notes']
            rows_html.append(f'''
        <tr class="{cls}">
          <td class="num">{h(notes_short)}</td>
          <td class="center">{h(r["date"])}</td>
          <td class="center status">{h(r["status"])}</td>
          <td class="num">{h(r["net"])}</td>
          <td class="num">{h(r["fee"])}</td>
          <td class="center">1</td>
          <td class="num">{h(r["total"] or r["net"])}</td>
          <td class="center ltr">{h(r["phone"])}</td>
          <td>{h(r["address"])}</td>
          <td></td>
          <td class="center ltr">{h(r["receipt_no"])}</td>
          <td class="center">{h(r["store"])}</td>
          <td class="center">{global_idx}</td>
        </tr>''')

    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "Tahoma", "Arial Unicode MS", "DejaVu Sans", Arial, sans-serif;
    font-size: 8pt;
    direction: rtl;
    color: #111;
  }}
  .page-header {{
    background: #2e86c1;
    color: white;
    padding: 6px 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2px;
  }}
  .page-header .title {{ font-size: 12pt; font-weight: bold; text-align: center; flex: 1; }}
  .page-header .side {{ font-size: 9pt; }}
  .sub-header {{
    background: #d6eaf8;
    padding: 4px 10px;
    font-size: 8pt;
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  th {{
    background: #4da6d9;
    color: white;
    font-size: 7.5pt;
    font-weight: bold;
    padding: 4px 2px;
    text-align: center;
    border: 0.5px solid #aed6f1;
    white-space: nowrap;
  }}
  td {{
    padding: 3px 2px;
    border: 0.5px solid #aed6f1;
    vertical-align: middle;
    font-size: 7.5pt;
    word-wrap: break-word;
    text-align: right;
  }}
  td.center {{ text-align: center; }}
  td.num {{ text-align: center; direction: ltr; }}
  td.ltr {{ direction: ltr; text-align: center; }}
  td.status {{ font-size: 7pt; }}
  tr.odd td  {{ background: #ffffff; }}
  tr.even td {{ background: #eaf4fb; }}
  tr.store-header td {{
    background: #1a5276;
    color: white;
    font-size: 9pt;
    padding: 5px 10px;
    text-align: right;
    border: none;
  }}
  .footer {{
    background: #1a5276;
    color: white;
    padding: 6px 10px;
    font-size: 9pt;
    font-weight: bold;
    text-align: center;
    margin-top: 6px;
  }}
  /* Column widths */
  col.c-notes   {{ width: 11%; }}
  col.c-date    {{ width: 8%;  }}
  col.c-status  {{ width: 8%;  }}
  col.c-net     {{ width: 6%;  }}
  col.c-fee     {{ width: 6%;  }}
  col.c-qty     {{ width: 4%;  }}
  col.c-total   {{ width: 6%;  }}
  col.c-phone   {{ width: 9%;  }}
  col.c-addr    {{ width: 19%; }}
  col.c-recip   {{ width: 6%;  }}
  col.c-recno   {{ width: 7%;  }}
  col.c-store   {{ width: 5%;  }}
  col.c-idx     {{ width: 3%;  }}
</style>
</head>
<body>
<div class="page-header">
  <div class="side">شركة كربلاء للتجارة</div>
  <div class="title">كشف حساب الواصل للتاجر — مرتّب حسب المتجر</div>
  <div class="side">أمير محمد اطراف</div>
</div>
<div class="sub-header">
  <span>إجمالي الطلبات: <strong>{len(records)}</strong> &nbsp;|&nbsp; عدد المتاجر: <strong>{len(groups)}</strong> &nbsp;|&nbsp; صفحات المصدر: <strong>{total_pages}</strong></span>
  <span>تاريخ التقرير: <strong>{today}</strong></span>
</div>

<table>
  <colgroup>
    <col class="c-notes"><col class="c-date"><col class="c-status">
    <col class="c-net"><col class="c-fee"><col class="c-qty">
    <col class="c-total"><col class="c-phone"><col class="c-addr">
    <col class="c-recip"><col class="c-recno"><col class="c-store"><col class="c-idx">
  </colgroup>
  <thead>
    <tr>
      <th>ملاحظات</th>
      <th>تاريخ الأدخال</th>
      <th>الحالة</th>
      <th>الصافي للتاجر</th>
      <th>أجرة التوصيل</th>
      <th>عدد القطع</th>
      <th>مبلغ الوصل</th>
      <th>رقم الهاتف</th>
      <th>العنوان</th>
      <th>أسم المستلم</th>
      <th>رقم الوصل</th>
      <th>المتجر</th>
      <th>#</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>

<div class="footer">
  مبلغ الوصولات بعد التوصيل: {grand_net:,} دينار عراقي
  &nbsp;&nbsp;|&nbsp;&nbsp;
  إجمالي الطلبات: {len(records)} &nbsp;|&nbsp; المتاجر: {len(groups)}
</div>
</body>
</html>'''

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) != 3:
        print('Usage: python3 generate_pdf.py <input.pdf> <output.pdf>', file=sys.stderr)
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]
    if not os.path.exists(input_path):
        print(f'ERROR: not found: {input_path}', file=sys.stderr); sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f'[py] Reading: {input_path}', file=sys.stderr)
    raw_records, total_pages = extract_rows(input_path)
    print(f'[py] Raw: {len(raw_records)}', file=sys.stderr)

    records, groups = sort_records(raw_records)
    print(f'[py] Valid: {len(records)} | Stores: {sorted(groups.keys())}', file=sys.stderr)

    if not records:
        print('ERROR: No records found', file=sys.stderr); sys.exit(1)

    # Write HTML to temp file
    html_content = build_html(records, groups, total_pages)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', encoding='utf-8', delete=False) as f:
        f.write(html_content)
        html_path = f.name

    print(f'[py] Converting HTML → PDF via wkhtmltopdf', file=sys.stderr)
    result = subprocess.run([
        'wkhtmltopdf',
        '--page-size', 'A4',
        '--orientation', 'Landscape',
        '--margin-top', '10mm',
        '--margin-bottom', '10mm',
        '--margin-left', '8mm',
        '--margin-right', '8mm',
        '--encoding', 'UTF-8',
        '--disable-smart-shrinking',
        '--footer-center', 'صفحة [page] من [topage]',
        '--footer-font-size', '7',
        '--footer-font-name', 'Tahoma',
        '--quiet',
        html_path,
        output_path,
    ], capture_output=True, text=True)

    os.unlink(html_path)

    if result.returncode != 0:
        print(f'wkhtmltopdf error: {result.stderr[:500]}', file=sys.stderr)
        sys.exit(1)

    print('[py] Done.', file=sys.stderr)
    stats = {'inputRows': len(raw_records), 'outputRows': len(records),
             'stores': len(groups), 'totalPages': total_pages}
    print(json.dumps(stats))

if __name__ == '__main__':
    main()
