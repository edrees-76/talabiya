"""Dashboard: today's KPIs, restaurant status, alerts, last days, month share, top items, price watch."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from talabiya.core import backup, ledger
from talabiya.core.money import fmt
from talabiya.gui import icons, theme
from talabiya.gui import widgets as W
from talabiya.gui.charts import ColumnChart, ProgressBar, ShareBar
from talabiya.gui.state import Page

SHORT_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def empty_state(page: Page) -> W.Card:
    c = W.Card()
    c.lay.setContentsMargins(24, 40, 24, 40)
    c.lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    c.lay.addWidget(W.logo("mark-clipboard.png", 110))
    h = W.label("ابدأ بإضافة أول مطعم", "h3")
    h.setAlignment(Qt.AlignmentFlag.AlignCenter)
    c.lay.addWidget(h)
    p = W.label("المنظومة فارغة. أضف المطاعم التي تشتري لها،\n"
                "ثم سجّل مشتريات كل يوم وأقفل اليوم بمقارنة الراجع بالموجود.", "muted")
    p.setAlignment(Qt.AlignmentFlag.AlignCenter)
    c.lay.addWidget(p, 0, Qt.AlignmentFlag.AlignHCenter)
    steps = QHBoxLayout()
    steps.addStretch(1)
    for i, s in enumerate(["أضف المطاعم", "راجع الأصناف", "سجّل مشتريات اليوم", "أقفل اليوم"], 1):
        steps.addWidget(W.Badge("new", f"{W.iso(f'{i}.')} {s}"))
    steps.addStretch(1)
    c.lay.addLayout(steps)
    b = W.button("إضافة مطعم", "fresh", "plus", on_click=lambda: page.state.go("rests"))
    c.lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
    return c


class Kpi(W.Card):
    def __init__(self, icon: str, title: str, value: QWidget | str, hint: str, gold: bool = False) -> None:
        super().__init__()
        top = QHBoxLayout()
        ic = QLabel()
        ic.setFixedSize(36, 36)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg = theme.t("surface_gold") if gold else theme.t("surface_tint")
        ic.setStyleSheet(f"background: {bg}; border-radius: 8px;")
        ic.setPixmap(icons.pixmap(icon, theme.t("on_gold") if gold else theme.t("brand"), 20))
        top.addWidget(ic)
        top.addWidget(W.label(title, "kpiLabel"))
        top.addStretch(1)
        self.lay.addLayout(top)
        if isinstance(value, str):
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(W.label(value, "kpi"))
            row.addWidget(W.label("د.ل", "muted"))
            self.lay.addLayout(row)
        else:
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(value)
            self.lay.addLayout(row)
        self.lay.addWidget(W.label(hint, "muted"))


def _table(rows: list[list[QWidget | str]], header: list[str] | None = None, num_cols: set[int] | None = None) -> QGridLayout:
    g = QGridLayout()
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    num_cols = num_cols or set()
    r0 = 0
    if header:
        for c, h in enumerate(header):
            lb = W.label(h, "kpiLabel")
            if c in num_cols:
                lb.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            g.addWidget(lb, 0, c)
        r0 = 1
    for r, row in enumerate(rows, r0):
        for c, cell in enumerate(row):
            w = cell if isinstance(cell, QWidget) else W.label(cell, "num" if c in num_cols else None)
            if c in num_cols and isinstance(w, QLabel):
                w.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            g.addWidget(w, r, c)
    g.setColumnStretch(0, 1)
    return g


class DashboardPage(Page):
    title = "لوحة القيادة"
    subtitle = "ملخص اليوم والأيام الأخيرة"
    uses_day = True

    def __init__(self, state) -> None:
        super().__init__(state)
        self.top_actions.addWidget(W.button("مشتريات اليوم", "primary", "cart", on_click=lambda: state.go("day")))
        self.host = QVBoxLayout()
        self.host.setSpacing(20)
        self.body.addLayout(self.host)
        self.body.addStretch(1)

    def refresh(self) -> None:
        W.clear_layout(self.host)
        rests = self.repo.restaurants()
        if not rests:
            self.host.addWidget(empty_state(self))
            return
        day = self.state.day
        sheets = {s.restaurant_id: s for s in self.repo.sheets_for_day(day.isoformat())}
        all_sheets = [sheets.get(r.id) or self.repo.sheet(day.isoformat(), r.id) for r in rests]
        extra = [s for rid, s in sheets.items() if rid not in {r.id for r in rests}]
        tot = ledger.day_totals(all_sheets + extra)
        dc = self.repo.day_close(day.isoformat())
        diff = ledger.difference(dc.actual_cash, tot.returned) if dc.closed else None

        # KPIs
        k = QGridLayout()
        k.setSpacing(20)
        k.addWidget(Kpi("wallet", "المستلم", fmt(tot.received), f"من {tot.restaurants_with_cash} مطاعم"), 0, 0)
        k.addWidget(Kpi("cart", "المصروفات", fmt(tot.expenses), f"{tot.lines} صنفاً مشترى"), 0, 1)
        k.addWidget(Kpi("return", "الراجع المتوقع", fmt(tot.returned), "المستلم − المصروفات", gold=True), 0, 2)
        k.addWidget(Kpi("scale", "الفرق", W.diff_badge(diff),
                        "أُقفل اليوم" if dc.closed else "يُحسب عند إقفال اليوم"), 0, 3)
        for c in range(4):
            k.setColumnStretch(c, 1)
        self.host.addLayout(k)

        # status + alerts
        row = QHBoxLayout()
        row.setSpacing(20)
        st = W.Card("حالة المطاعم", "store", "اضغط على المطعم لفتح مشترياته")
        for i, r in enumerate(rests):
            s = sheets.get(r.id) or self.repo.sheet(day.isoformat(), r.id)
            st.lay.addWidget(self._rest_row(r.id, r.name, s))
            if i < len(rests) - 1:
                st.lay.addWidget(W.hline())
        st.lay.addStretch(1)
        row.addWidget(st, 3)
        al = W.Card("تنبيهات", "alert")
        for a in self._alerts(rests, sheets, day):
            al.lay.addWidget(a)
        al.lay.addStretch(1)
        row.addWidget(al, 2)
        self.host.addLayout(row)

        # last days + month share
        row2 = QHBoxLayout()
        row2.setSpacing(20)
        ch = W.Card("المصروفات — آخر 7 أيام", "cart", "بالدينار، كل المطاعم")
        chart = ColumnChart()
        chart.set_data([(SHORT_DAYS[date.fromisoformat(d).weekday()], v)
                        for d, v in self.repo.daily_expenses(day, 7)])
        ch.lay.addWidget(chart)
        row2.addWidget(ch, 3)
        m0 = day.replace(day=1)
        m1 = (m0 + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        share = self.repo.month_by_restaurant(m0, m1)
        ms = W.Card("مصروفات الشهر حسب المطعم", "store", f"{W.MONTHS[day.month - 1]} {day.year}")
        if share:
            bar = ShareBar()
            bar.set_values([v for _, v in share])
            ms.lay.addWidget(bar)
            total = sum(v for _, v in share)
            rows = []
            for i, (name, v) in enumerate(share):
                dot = QLabel()
                dot.setFixedSize(10, 10)
                dot.setStyleSheet(f"background: {ShareBar.color(i)}; border-radius: 3px;")
                cell = QWidget()
                cl = QHBoxLayout(cell)
                cl.setContentsMargins(0, 0, 0, 0)
                cl.addWidget(dot)
                cl.addWidget(QLabel(name), 1)
                rows.append([cell, fmt(v), f"{round(v / total * 100)}%" if total else "0%"])
            rows.append([W.label("المجموع", "label"), W.label(fmt(total), "num"), ""])
            ms.lay.addLayout(_table(rows, num_cols={1, 2}))
        else:
            ms.lay.addWidget(W.label("لا توجد مشتريات هذا الشهر بعد", "muted"))
        ms.lay.addStretch(1)
        row2.addWidget(ms, 2)
        self.host.addLayout(row2)

        # top items + price watch
        row3 = QHBoxLayout()
        row3.setSpacing(20)
        ti = W.Card("أعلى الأصناف تكلفة هذا الشهر", "list")
        top = self.repo.top_items(m0, m1)
        if top:
            ti.lay.addLayout(_table([[t.item, t.qty_text, fmt(t.total)] for t in top],
                                    ["الصنف", "الكمية", "المجموع (د.ل)"], {2}))
        else:
            ti.lay.addWidget(W.label("لا توجد مشتريات هذا الشهر بعد", "muted"))
        ti.lay.addStretch(1)
        row3.addWidget(ti, 1)
        pw = W.Card("متابعة الأسعار", "coins", "آخر سعر مقابل السابق")
        changes = self.repo.price_changes(day.isoformat())
        if changes:
            rows = []
            for c in changes:
                pct = c.change_pct
                if pct > 0.05:
                    ch_w = self._trend("up", f"ارتفاع {W.iso(f'{pct:.0f}%')}")
                elif pct < -0.05:
                    ch_w = self._trend("down", f"انخفاض {W.iso(f'{-pct:.0f}%')}")
                else:
                    ch_w = W.label("ثابت", "muted")
                rows.append([f"{c.item} ({c.unit})" if c.unit else c.item, fmt(c.previous), fmt(c.latest), ch_w])
            pw.lay.addLayout(_table(rows, ["الصنف", "السابق", "الأخير", "التغير"], {1, 2}))
        else:
            pw.lay.addWidget(W.label("تظهر هنا الأسعار بعد شراء الصنف مرتين على الأقل", "muted", wrap=True))
        pw.lay.addStretch(1)
        row3.addWidget(pw, 1)
        self.host.addLayout(row3)

    @staticmethod
    def _trend(kind: str, text: str) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(kind, theme.t("danger" if kind == "up" else "green_strong"), 16))
        lay.addWidget(ic)
        lay.addWidget(W.label(text, kind))
        lay.addStretch(1)
        return w

    def _rest_row(self, rid: int, name: str, s) -> QWidget:
        w = QFrame()
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        w.setToolTip("فتح مشتريات هذا المطعم")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(W.label(name, "h2"))
        top.addStretch(1)
        top.addWidget(W.state_badge(ledger.sheet_state(s).value))
        lay.addLayout(top)
        spent = ledger.expenses(s)
        lay.addWidget(ProgressBar(spent / s.received if s.received else (1.01 if spent else 0)))
        meta = QHBoxLayout()
        meta.setSpacing(18)
        for cap, v in (("المستلم", s.received), ("المصروف", spent), ("المتبقي", ledger.remaining(s))):
            meta.addWidget(W.label(f"{cap}  {W.money_text(v)}", "muted"))
        meta.addStretch(1)
        lay.addLayout(meta)
        w.mouseReleaseEvent = lambda _e: self.state.go("day", restaurant_id=rid)  # type: ignore[method-assign]
        return w

    def _alerts(self, rests, sheets, day: date) -> list[QWidget]:
        out: list[QWidget] = []
        if day == date.today():
            for r in rests:
                s = sheets.get(r.id)
                if s is None or not s.received:
                    out.append(W.Alert("warn", "pause", f"{r.name}: لم يُسجَّل مستلم اليوم",
                                       ("فتح", lambda rid=r.id: self.state.go("day", restaurant_id=rid))))
        for s in sheets.values():
            if s.received and ledger.remaining(s) < 0:
                name = next((r.name for r in rests if r.id == s.restaurant_id), "")
                out.append(W.Alert("bad", "alert", f"{name}: المصروف أكبر من المستلم بـ {fmt(-ledger.remaining(s))}"))
        for d in self.repo.unclosed_days(day.isoformat(), 3):
            dd = date.fromisoformat(d)
            out.append(W.Alert("warn", "clock", f"يوم {W.day_label(dd)} لم يُقفل بعد",
                               ("إقفال", lambda dd=dd: self.state.go("close", day=dd))))
        ups = [c for c in self.repo.price_changes(day.isoformat(), 50)
               if c.latest_day == day.isoformat() and c.change_pct >= 10]
        ups.sort(key=lambda c: c.change_pct, reverse=True)
        for c in ups[:2]:
            out.append(W.Alert("bad", "up", f"{c.item}: ارتفع {W.iso(f'{c.change_pct:.0f}%')} عن آخر شراء"))
        if len(ups) > 2:
            out.append(W.Alert("bad", "up", f"وهناك {W.iso(str(len(ups) - 2))} أصناف أخرى ارتفع سعرها {W.iso('10%')} أو أكثر — انظر «متابعة الأسعار»"))
        last = backup.last_backup(self.repo)
        if backup.folder(self.repo) is None:
            out.append(W.Alert("warn", "save", "لم يُختر مجلد للنسخ الاحتياطي",
                               ("الإعدادات", lambda: self.state.go("settings"))))
        elif backup.frequency(self.repo) == "off":
            out.append(W.Alert("warn", "save", "النسخ الاحتياطي التلقائي متوقف",
                               ("الإعدادات", lambda: self.state.go("settings"))))
        elif last is None:
            out.append(W.Alert("warn", "save", "لم تُؤخذ أي نسخة احتياطية بعد"))
        else:
            when = "اليوم" if last.date() == datetime.now().date() else last.date().isoformat()
            out.append(W.Alert("ok", "check", f"آخر نسخة احتياطية: {when} {last.strftime('%H:%M')}"))
        if len(out) == 1 and out[0] is not None and isinstance(out[0], W.Alert):
            out.insert(0, W.Alert("ok", "check", "لا توجد تنبيهات"))
        return out
