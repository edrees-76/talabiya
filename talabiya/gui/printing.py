"""Printable summaries (HTML -> QTextDocument) with print preview and PDF export."""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QFileDialog, QWidget

from talabiya.core import ledger
from talabiya.core.models import DayClose, Sheet
from talabiya.core.money import fmt, qty_text
from talabiya.gui import theme
from talabiya.gui import widgets as W

_CSS = """
body { font-family: 'Tajawal'; font-size: 11pt; color: #0a2a55; }
h1 { font-family: 'Cairo'; font-size: 17pt; color: #063b78; margin: 0; }
.muted { color: #44566f; }
table { border-collapse: collapse; width: 100%; }
th { background: #f3f7fc; color: #44566f; font-weight: bold; padding: 6px; border-bottom: 2px solid #d5dfec; }
td { padding: 6px; border-bottom: 1px solid #d5dfec; }
td.n, th.n { text-align: left; font-family: 'Segoe UI'; }
.tot td { font-weight: bold; background: #f3f7fc; }
.big { font-size: 15pt; font-weight: bold; color: #063b78; }
.bad { color: #b3201c; font-weight: bold; }
.ok { color: #1f7a1c; font-weight: bold; }
"""


def _head(title: str, day: str) -> str:
    d = date.fromisoformat(day)
    return (f'<table width="100%"><tr><td style="border:0"><h1>{escape(title)}</h1>'
            f'<span class="muted">{W.weekday(d)} {day}</span></td>'
            f'<td style="border:0" align="left"><img src="logo" width="170"></td></tr></table><br>')


def sheet_html(s: Sheet, restaurant: str) -> str:
    rows = []
    for i, ln in enumerate(s.lines, 1):
        rows.append(f"<tr><td>{i}</td><td>{escape(ln.item)}</td><td class='n'>{qty_text(ln.qty)}</td>"
                    f"<td>{escape(ln.unit)}</td><td class='n'>{fmt(ln.unit_price)}</td>"
                    f"<td class='n'>{fmt(ln.total)}</td></tr>")
    p = ledger.purchases(s.lines)
    rem = ledger.remaining(s)
    cls = "bad" if rem < 0 else "big"
    notes = f"<p><b>ملاحظات:</b> {escape(s.notes)}</p>" if s.notes else ""
    return f"""<html dir="rtl"><head><style>{_CSS}</style></head><body dir="rtl">
{_head("قائمة مشتريات " + restaurant, s.day)}
<table><tr><th>#</th><th>البيان</th><th class="n">الكمية</th><th>الوحدة</th><th class="n">سعر الوحدة</th>
<th class="n">الإجمالي</th></tr>{''.join(rows)}
<tr class="tot"><td></td><td colspan="4">مجموع المشتريات</td><td class="n">{fmt(p)}</td></tr></table><br>
<table width="55%">
<tr><td>المبلغ المستلم</td><td class="n">{fmt(s.received)}</td></tr>
<tr><td>مجموع المشتريات</td><td class="n">{fmt(p)}</td></tr>
<tr><td>يومية ادريس</td><td class="n">{fmt(s.wage)}</td></tr>
<tr><td>رسم دخول + تحميل</td><td class="n">{fmt(s.entry_fee)}</td></tr>
<tr class="tot"><td>إجمالي المصروفات</td><td class="n">{fmt(ledger.expenses(s))}</td></tr>
<tr><td><b>المبلغ المتبقي</b></td><td class="n"><span class="{cls}">{fmt(rem)} د.ل</span></td></tr>
</table>{notes}</body></html>"""


def close_html(day: str, rows: list[tuple[str, Sheet]], dc: DayClose) -> str:
    t = ledger.day_totals([s for _, s in rows])
    body = "".join(
        f"<tr><td>{escape(n)}</td><td class='n'>{fmt(s.received)}</td><td class='n'>{fmt(ledger.expenses(s))}</td>"
        f"<td class='n'>{fmt(ledger.remaining(s))}</td></tr>" for n, s in rows)
    diff = ledger.difference(dc.actual_cash, t.returned)
    if diff is None:
        dtxt = "<span class='muted'>لم يُدخل المبلغ الموجود</span>"
    elif diff == 0:
        dtxt = "<span class='ok'>مطابق — لا يوجد فرق</span>"
    elif diff < 0:
        dtxt = f"<span class='bad'>عجز {fmt(-diff)} د.ل</span>"
    else:
        dtxt = f"<span class='big'>زيادة {fmt(diff)} د.ل</span>"
    actual = "—" if dc.actual_cash is None else fmt(dc.actual_cash)
    state = "مُقفل" if dc.closed else "غير مُقفل"
    notes = f"<p><b>ملاحظات:</b> {escape(dc.notes)}</p>" if dc.notes else ""
    return f"""<html dir="rtl"><head><style>{_CSS}</style></head><body dir="rtl">
{_head("إقفال اليوم", day)}
<table><tr><th>المطعم</th><th class="n">المستلم</th><th class="n">المصروفات</th><th class="n">المتبقي</th></tr>
{body}<tr class="tot"><td>الإجمالي</td><td class="n">{fmt(t.received)}</td><td class="n">{fmt(t.expenses)}</td>
<td class="n">{fmt(t.returned)}</td></tr></table><br>
<table width="55%">
<tr><td>إجمالي الراجع</td><td class="n">{fmt(t.returned)}</td></tr>
<tr><td>المبلغ الموجود فعلياً</td><td class="n">{actual}</td></tr>
<tr class="tot"><td>الفرق</td><td>{dtxt}</td></tr>
<tr><td>الحالة</td><td>{state}</td></tr>
</table>{notes}</body></html>"""


def document(html: str) -> QTextDocument:
    doc = QTextDocument()
    doc.setDefaultTextOption(doc.defaultTextOption())
    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("logo"), QImage(theme.asset("logo-horizontal.jpg")))
    doc.setHtml(html)
    opt = doc.defaultTextOption()
    opt.setTextDirection(Qt.LayoutDirection.RightToLeft)
    doc.setDefaultTextOption(opt)
    return doc


def _printer(mode=QPrinter.PrinterMode.HighResolution) -> QPrinter:
    pr = QPrinter(mode)
    pr.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                 QMarginsF(14, 14, 14, 14), QPageLayout.Unit.Millimeter))
    return pr


def preview(parent: QWidget, html: str) -> None:
    doc = document(html)
    pr = _printer()
    dlg = QPrintPreviewDialog(pr, parent)
    dlg.setWindowTitle("معاينة الطباعة")
    dlg.resize(900, 900)
    dlg.paintRequested.connect(doc.print_)
    dlg.exec()


def write_pdf(html: str, path: Path) -> None:
    pr = _printer()
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(str(path))
    document(html).print_(pr)


def save_pdf(parent: QWidget, html: str, suggested: str) -> Path | None:
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    path, _ = QFileDialog.getSaveFileName(parent, "حفظ PDF", str(Path(docs) / suggested), "PDF (*.pdf)")
    if not path:
        return None
    p = Path(path if path.lower().endswith(".pdf") else path + ".pdf")
    write_pdf(html, p)
    W.info(parent, f"حُفظ الملف:\n{p}")
    return p
