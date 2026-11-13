"""Day close: what each restaurant should return vs the cash actually in hand."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from talabiya.core import ledger
from talabiya.core.money import fmt
from talabiya.gui import icons, printing, theme
from talabiya.gui import widgets as W
from talabiya.gui.pages.dashboard import empty_state
from talabiya.gui.state import Page


def close_rows(repo, day: str):
    """[(name, sheet)] for active restaurants plus any inactive one with data that day."""
    sheets = {s.restaurant_id: s for s in repo.sheets_for_day(day)}
    out = []
    for r in repo.restaurants(include_inactive=True):
        if r.active or r.id in sheets:
            out.append((r.name, sheets.get(r.id) or repo.sheet(day, r.id)))
    return out


class ClosePage(Page):
    title = "إقفال اليوم"
    subtitle = "قارن الراجع من كل المطاعم بالمبلغ الموجود معك"
    uses_day = True

    def __init__(self, state) -> None:
        super().__init__(state)
        self.host = QVBoxLayout()
        self.body.addLayout(self.host)
        self.body.addStretch(1)

    def refresh(self) -> None:
        W.clear_layout(self.host)
        if not self.repo.restaurants(include_inactive=True):
            self.host.addWidget(empty_state(self))
            return
        day = self.state.day_iso
        rows = close_rows(self.repo, day)
        self.totals = ledger.day_totals([s for _, s in rows])
        self.dc = self.repo.day_close(day)

        row = QHBoxLayout()
        row.setSpacing(20)
        card = W.Card("الراجع من المطاعم", "return")
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(10)
        for c, h in enumerate(["المطعم", "المستلم", "المصروفات", "المتبقي", "الحالة"]):
            lb = W.label(h, "kpiLabel")
            g.addWidget(lb, 0, c)
        for i, (name, s) in enumerate(rows, 1):
            g.addWidget(W.label(name), i, 0)
            for c, v in ((1, s.received), (2, ledger.expenses(s)), (3, ledger.remaining(s))):
                lb = W.label(fmt(v), "num")
                lb.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                g.addWidget(lb, i, c)
            g.addWidget(W.state_badge(ledger.sheet_state(s).value), i, 4, Qt.AlignmentFlag.AlignRight)
        n = len(rows) + 1
        g.addWidget(W.hline(), n, 0, 1, 5)
        g.addWidget(W.label("الإجمالي", "label"), n + 1, 0)
        for c, v in ((1, self.totals.received), (2, self.totals.expenses)):
            lb = W.label(fmt(v), "num")
            lb.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            g.addWidget(lb, n + 1, c)
        g.addWidget(W.Badge("gold", f"{fmt(self.totals.returned)} د.ل"), n + 1, 3, Qt.AlignmentFlag.AlignLeft)
        g.setColumnStretch(0, 1)
        card.lay.addLayout(g)
        card.lay.addStretch(1)
        row.addWidget(card, 1)

        side = QVBoxLayout()
        side.setSpacing(14)
        f = W.Card()
        f.lay.addWidget(W.label("المبلغ الموجود فعلياً", "label"))
        self.actual = W.MoneyEdit()
        if self.dc.actual_cash is not None:
            self.actual.set_value(self.dc.actual_cash, blank_zero=False)
        self.actual.valueChanged.connect(self._diff)
        f.lay.addWidget(self.actual)
        f.lay.addWidget(W.label("ملاحظات", "label"))
        self.notes = QPlainTextEdit(self.dc.notes)
        self.notes.setPlaceholderText("سبب الفرق إن وجد")
        self.notes.setFixedHeight(70)
        f.lay.addWidget(self.notes)
        side.addWidget(f)
        self.diff_box = QWidget()
        self.diff_box.setObjectName("diffBox")
        dl = QVBoxLayout(self.diff_box)
        dl.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        self.diff_icon = QLabel()
        top.addWidget(self.diff_icon)
        self.diff_cap = W.label("", "label")
        top.addWidget(self.diff_cap)
        top.addStretch(1)
        dl.addLayout(top)
        vr = QHBoxLayout()
        vr.addStretch(1)
        self.diff_val = W.label("", "big")
        vr.addWidget(self.diff_val)
        self.diff_cur = W.label("د.ل", "muted")
        vr.addWidget(self.diff_cur)
        dl.addLayout(vr)
        side.addWidget(self.diff_box)
        if self.dc.closed:
            side.addWidget(W.Alert("ok", "lock", f"أُقفل اليوم في {self.dc.closed_at or ''}".replace("T", " ")))
        acts = QHBoxLayout()
        if self.dc.closed:
            acts.addWidget(W.button("حفظ التعديل", "primary", "save", on_click=self._close))
            acts.addWidget(W.button("إعادة فتح اليوم", icon="unlock", on_click=self._reopen))
        else:
            acts.addWidget(W.button("إقفال اليوم", "primary", "lock", on_click=self._close))
        acts.addWidget(W.button("طباعة", icon="print", on_click=self._print))
        acts.addWidget(W.button("PDF", icon="pdf", on_click=self._pdf))
        side.addLayout(acts)
        side.addStretch(1)
        sw = QWidget()
        sw.setLayout(side)
        sw.setFixedWidth(380)
        row.addWidget(sw)
        self.host.addLayout(row)
        self._diff()

    def _diff(self) -> None:
        txt = self.actual.text().strip()
        if not txt:
            kind, cap, ic, val = "surface_gold", "أدخل المبلغ الموجود لحساب الفرق", "clock", None
        else:
            d = self.actual.value() - self.totals.returned
            if d == 0:
                kind, cap, ic, val = "surface_fresh", "مطابق — لا يوجد فرق", "check", 0
            elif d < 0:
                kind, cap, ic, val = "surface_alert", "عجز", "alert", -d
            else:
                kind, cap, ic, val = "surface_gold", "زيادة", "up", d
        fg = {"surface_fresh": "green_strong", "surface_alert": "danger", "surface_gold": "ink"}[kind]
        self.diff_box.setStyleSheet(f"#diffBox {{ background: {theme.t(kind)}; border-radius: 22px; }}")
        self.diff_icon.setPixmap(icons.pixmap(ic, theme.t(fg), 20))
        self.diff_cap.setText(cap)
        self.diff_cap.setStyleSheet(f"color: {theme.t(fg)};")
        self.diff_val.setVisible(val is not None)
        self.diff_cur.setVisible(val is not None)
        if val is not None:
            self.diff_val.setText(fmt(val))
            W.set_role(self.diff_val, {"surface_fresh": "bigOk", "surface_alert": "bigBad"}.get(kind, "big"))

    def _save_draft(self) -> None:
        if not hasattr(self, "actual"):
            return
        txt = self.actual.text().strip()
        dc = self.repo.day_close(self.state.day_iso)
        dc.actual_cash = self.actual.value() if txt else None
        dc.notes = self.notes.toPlainText().strip()
        self.repo.save_day_close(dc)

    def _close(self) -> None:
        if not self.actual.text().strip():
            W.error(self, "أدخل المبلغ الموجود فعلياً قبل إقفال اليوم")
            self.actual.setFocus()
            return
        self.repo.close_day(self.state.day_iso, self.actual.value(), self.notes.toPlainText().strip())
        self.state.dataChanged.emit()
        self.refresh()

    def _reopen(self) -> None:
        if W.confirm(self, "إعادة فتح اليوم تلغي الإقفال وتبقي المبلغ المسجل. هل تريد المتابعة؟"):
            self._save_draft()
            self.repo.reopen_day(self.state.day_iso)
            self.state.dataChanged.emit()
            self.refresh()

    def leave(self) -> bool:
        if hasattr(self, "actual") and not self.repo.day_close(self.state.day_iso).closed:
            self._save_draft()
        return True

    def _html(self) -> str:
        self._save_draft()
        day = self.state.day_iso
        return printing.close_html(day, close_rows(self.repo, day), self.repo.day_close(day))

    def _print(self) -> None:
        printing.preview(self, self._html())

    def _pdf(self) -> None:
        printing.save_pdf(self, self._html(), f"{self.state.day_iso} - إقفال اليوم.pdf")
