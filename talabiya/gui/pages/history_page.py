"""All past days: open one to edit it, or delete it."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QAbstractItemView, QDateEdit, QHBoxLayout, QHeaderView, QTableWidget, QTableWidgetItem, QWidget

from talabiya.core import ledger
from talabiya.core.money import fmt
from talabiya.gui import widgets as W
from talabiya.gui.state import Page

COLS = ["التاريخ", "اليوم", "المطاعم", "المستلم", "المصروفات", "الراجع", "الإقفال", ""]


def _qd(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _py(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class HistoryPage(Page):
    title = "السجل"
    subtitle = "كل الأيام المسجلة. افتح أي يوم لتعديله أو احذفه"

    def __init__(self, state) -> None:
        super().__init__(state)
        today = date.today()
        self.start = QDateEdit(_qd(today.replace(day=1) - timedelta(days=31)))
        self.end = QDateEdit(_qd(today))
        for cap, e in (("من", self.start), ("إلى", self.end)):
            e.setCalendarPopup(True)
            e.setDisplayFormat("yyyy-MM-dd")
            e.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            e.dateChanged.connect(lambda _d: self.refresh())
            self.top_actions.addWidget(W.label(cap, "label"))
            self.top_actions.addWidget(e)
        card = W.Card()
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(64)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for c, wdt in ((6, 190), (7, 150)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, wdt)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._open(self.rows[r].day))
        self.table.setMinimumHeight(500)
        card.lay.addWidget(self.table)
        self.sum_lb = W.label("", "muted")
        card.lay.addWidget(self.sum_lb)
        self.body.addWidget(card, 1)

    def refresh(self) -> None:
        s, e = _py(self.start.date()), _py(self.end.date())
        self.rows = self.repo.history(s.isoformat(), e.isoformat())
        self.table.setRowCount(0)
        for i, h in enumerate(self.rows):
            self.table.insertRow(i)
            d = date.fromisoformat(h.day)
            vals = [h.day, W.weekday(d), str(h.restaurants), fmt(h.received), fmt(h.expenses), fmt(h.returned)]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c in (0, 2, 3, 4, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, c, it)
            diff = ledger.difference(h.actual_cash, h.returned) if h.closed else None
            bw = QWidget()
            bl = QHBoxLayout(bw)
            bl.setContentsMargins(4, 0, 4, 0)
            bl.addWidget(W.diff_badge(diff, "لم يُقفل"))
            bl.addStretch(1)
            self.table.setCellWidget(i, 6, bw)
            aw = QWidget()
            al = QHBoxLayout(aw)
            al.setContentsMargins(4, 0, 4, 0)
            al.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            ob = W.button("فتح", small=True, icon="open", on_click=lambda dd=h.day: self._open(dd))
            al.addWidget(ob)
            al.addWidget(W.icon_button("trash", "حذف اليوم", lambda dd=h.day: self._delete(dd), "danger"))
            al.addStretch(1)
            self.table.setCellWidget(i, 7, aw)
        if not self.rows:
            self.sum_lb.setText("لا توجد أيام مسجلة في هذه الفترة")
        else:
            exp = sum(h.expenses for h in self.rows)
            self.sum_lb.setText(f"{len(self.rows)} يوماً — مجموع المصروفات {W.money_text(exp)}")

    def _open(self, day: str) -> None:
        self.state.go("day", day=date.fromisoformat(day))

    def _delete(self, day: str) -> None:
        d = date.fromisoformat(day)
        if W.confirm(self, f"سيُحذف يوم {W.day_label(d)} بكل مشترياته وإقفاله، ولا يمكن التراجع إلا من نسخة "
                           "احتياطية. هل تريد الحذف؟", "حذف اليوم", danger=True):
            self.repo.delete_day(day)
            self.state.dataChanged.emit()
            self.refresh()
