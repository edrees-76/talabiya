"""Purchases of the selected day: one tab per restaurant, lines table, cash fields. Saves automatically."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTabBar,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from talabiya.core import ledger
from talabiya.core.models import Line, Sheet
from talabiya.core.money import fmt, line_total
from talabiya.gui import printing, theme
from talabiya.gui import widgets as W
from talabiya.gui.pages.dashboard import empty_state
from talabiya.gui.state import Page

COLS = ["#", "البيان", "الكمية", "الوحدة", "سعر الوحدة", "الإجمالي", ""]


class _Row:
    def __init__(self, page: DayPage, line: Line) -> None:
        self.page = page
        self.item = QComboBox()
        self.item.setEditable(True)
        self.item.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item.addItems(page.item_names)
        self.item.setCurrentIndex(-1)
        self.item.setEditText(line.item)
        self.item.lineEdit().setPlaceholderText("اكتب أو اختر صنفاً")
        comp = QCompleter(page.item_names, self.item)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.item.setCompleter(comp)
        self.qty = W.QtyEdit()
        self.qty.set_value(line.qty)
        self.unit = QComboBox()
        self.unit.addItem("")
        self.unit.addItems(page.units)
        if line.unit and self.unit.findText(line.unit) < 0:
            self.unit.addItem(line.unit)
        self.unit.setCurrentText(line.unit)
        self.price = W.MoneyEdit()
        self.price.set_value(line.unit_price)
        self.total = W.MoneyEdit()
        self.total.setToolTip("يُحسب تلقائياً (الكمية × السعر). اكتب فيه لتثبيت إجمالي يدوي، وامسحه للرجوع للحساب")
        self.manual: int | None = line.total_override
        self._show_total()
        self.note = line.note
        for w in (self.item, self.qty, self.unit, self.price, self.total):
            w.installEventFilter(page)
        self.item.lineEdit().installEventFilter(page)
        self.item.currentTextChanged.connect(lambda _t: page.changed())
        self.item.activated.connect(lambda _i: self._default_unit())
        self.item.lineEdit().editingFinished.connect(self._default_unit)
        self.qty.valueChanged.connect(self._recalc)
        self.price.valueChanged.connect(self._recalc)
        self.unit.currentTextChanged.connect(lambda _t: page.changed())
        self.total.textEdited.connect(self._total_edited)

    def _default_unit(self) -> None:
        if not self.unit.currentText():
            u = self.page.default_units.get(self.item.currentText().strip())
            if u:
                if self.unit.findText(u) < 0:
                    self.unit.addItem(u)
                self.unit.setCurrentText(u)

    def _total_edited(self, text: str) -> None:
        self.manual = None if not text.strip() else self.total.value()
        self._mark_manual()
        self.page.changed()

    def _mark_manual(self) -> None:
        self.total.setProperty("manual", self.manual is not None)
        W.repolish(self.total)

    def _show_total(self) -> None:
        if self.manual is None:
            self.total.set_value(line_total(self.qty.value(), self.price.value()), blank_zero=False)
        else:
            self.total.set_value(self.manual, blank_zero=False)
        self._mark_manual()

    def _recalc(self) -> None:
        if self.manual is None:
            self.total.set_value(line_total(self.qty.value(), self.price.value()), blank_zero=False)
        self.page.changed()

    def line(self) -> Line:
        return Line(self.item.currentText().strip(), self.qty.value(), self.unit.currentText(), self.price.value(),
                    self.manual, self.note)


class DayPage(Page):
    title = "مشتريات اليوم"
    subtitle = "سجّل ما اشتريته لكل مطعم. الحفظ تلقائي"
    uses_day = True

    def __init__(self, state) -> None:
        super().__init__(state)
        self.sheet: Sheet | None = None
        self.rows: list[_Row] = []
        self.rest_ids: list[int] = []
        self.dirty = False
        self.loading = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.save)

        self.empty_host = QVBoxLayout()
        self.body.addLayout(self.empty_host)
        self.main = QWidget()
        ml = QVBoxLayout(self.main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(16)
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.currentChanged.connect(self._tab_changed)
        ml.addWidget(self.tabs)

        row = QHBoxLayout()
        row.setSpacing(20)
        # lines
        self.lines_card = W.Card("", None)
        head = QHBoxLayout()
        self.rest_title = W.label("", "h2")
        head.addWidget(self.rest_title)
        head.addStretch(1)
        self.badge_host = QHBoxLayout()
        head.addLayout(self.badge_host)
        self.lines_card.lay.addLayout(head)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c, wdt in ((0, 34), (2, 84), (3, 104), (4, 104), (5, 116), (6, 44)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, wdt)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.setMinimumHeight(360)
        self.lines_card.lay.addWidget(self.table, 1)
        brow = QHBoxLayout()
        brow.addWidget(W.button("أضف صنفاً", "fresh", "plus", on_click=self.add_row,
                                tip="إضافة بند جديد (Ctrl+N)"))
        brow.addStretch(1)
        brow.addWidget(W.label("الإجمالي المظلل بالأصفر مكتوب يدوياً", "muted"))
        self.lines_card.lay.addLayout(brow)
        row.addWidget(self.lines_card, 1)

        # side
        side = QVBoxLayout()
        side.setSpacing(14)
        cash = W.Card()
        self.received = W.MoneyEdit()
        self.wage = W.MoneyEdit()
        self.fee = W.MoneyEdit()
        for cap, w in (("المبلغ المستلم", self.received), ("يومية ادريس", self.wage),
                       ("رسم دخول + تحميل", self.fee)):
            cash.lay.addWidget(W.label(cap, "label"))
            cash.lay.addWidget(w)
            w.valueChanged.connect(self.changed)
        cash.lay.addWidget(W.label("ملاحظات", "label"))
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(64)
        self.notes.textChanged.connect(self.changed)
        cash.lay.addWidget(self.notes)
        side.addWidget(cash)
        summ = W.Card()
        self.sum_lines = W.label("", None)
        self.sum_fixed = W.label("", None)
        self.sum_total = W.label("", "label")
        self.sum_count = W.label("المشتريات", "kpiLabel")
        for cap, lb in ((self.sum_count, self.sum_lines), (W.label("يومية + رسوم", "kpiLabel"), self.sum_fixed),
                        (W.label("إجمالي المصروفات", "kpiLabel"), self.sum_total)):
            r = QHBoxLayout()
            r.addWidget(cap)
            r.addStretch(1)
            r.addWidget(lb)
            summ.lay.addLayout(r)
        box = QWidget()
        box.setObjectName("remainBox")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 12, 16, 12)
        self.remain_cap = W.label("المتبقي", "label")
        bl.addWidget(self.remain_cap)
        rr = QHBoxLayout()
        rr.addStretch(1)
        self.remain = W.label("", "big")
        rr.addWidget(self.remain)
        rr.addWidget(W.label("د.ل", "muted"))
        bl.addLayout(rr)
        self.remain_box = box
        summ.lay.addWidget(box)
        side.addWidget(summ)
        acts = QHBoxLayout()
        self.done_btn = W.button("تم الشراء", "primary", "check", on_click=self._toggle_done,
                                 tip="يعلّم مشتريات هذا المطعم مكتملة")
        acts.addWidget(self.done_btn)
        acts.addWidget(W.button("طباعة", icon="print", on_click=self._print))
        acts.addWidget(W.button("PDF", icon="pdf", on_click=self._pdf, tip="حفظ الملخص ملف PDF"))
        side.addLayout(acts)
        self.saved_lb = W.label("", "muted")
        side.addWidget(self.saved_lb)
        side.addStretch(1)
        sw = QWidget()
        sw.setLayout(side)
        sw.setFixedWidth(300)
        row.addWidget(sw)
        ml.addLayout(row, 1)
        self.body.addWidget(self.main, 1)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_row)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self._print)

    # ------------------------------------------------------------ loading
    def refresh(self) -> None:
        self.save()
        W.clear_layout(self.empty_host)
        rests = self.repo.restaurants()
        day = self.state.day_iso
        saved = {s.restaurant_id for s in self.repo.sheets_for_day(day)}
        inactive_with_data = [r for r in self.repo.restaurants(include_inactive=True)
                              if not r.active and r.id in saved]
        rests = rests + inactive_with_data
        if not rests:
            self.main.hide()
            self.empty_host.addWidget(empty_state(self))
            return
        self.main.show()
        self.item_names = [i.name for i in self.repo.items()]
        self.default_units = {i.name: i.default_unit for i in self.repo.items(include_inactive=True)}
        self.units = self.repo.units()
        self.rest_ids = [r.id for r in rests]
        self.rest_names = {r.id: r.name for r in rests}
        want = self.state.restaurant_id if self.state.restaurant_id in self.rest_ids else self.rest_ids[0]
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        for r in rests:
            self.tabs.addTab(self._tab_text(r.id, r.name))
        self.tabs.setCurrentIndex(self.rest_ids.index(want))
        self.tabs.blockSignals(False)
        self._load(want)

    def _tab_text(self, rid: int, name: str) -> str:
        s = self.repo.sheet(self.state.day_iso, rid)
        n = len(s.lines)
        mark = " ✓" if s.done else ""
        return f"{name}  ({n}){mark}"

    def _tab_changed(self, i: int) -> None:
        if 0 <= i < len(self.rest_ids):
            self.save()
            self.state.restaurant_id = self.rest_ids[i]
            self._load(self.rest_ids[i])

    def _load(self, rid: int) -> None:
        self.loading = True
        self.state.restaurant_id = rid
        self.sheet = self.repo.sheet(self.state.day_iso, rid)
        s = self.sheet
        self.rest_title.setText(self.rest_names.get(rid, ""))
        self.received.set_value(s.received)
        self.wage.set_value(s.wage)
        self.fee.set_value(s.entry_fee)
        self.notes.setPlainText(s.notes)
        self.table.setRowCount(0)
        self.rows = []
        for ln in s.lines:
            self._append(ln)
        if not s.lines:
            self._append(Line(""))
        self.loading = False
        self.dirty = False
        self.saved_lb.setText("")
        self._update_summary()

    # ------------------------------------------------------------ rows
    def _append(self, line: Line) -> _Row:
        r = _Row(self, line)
        i = self.table.rowCount()
        self.table.insertRow(i)
        num = W.label(str(i + 1), "muted")
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(i, 0, num)
        self.table.setCellWidget(i, 1, r.item)
        self.table.setCellWidget(i, 2, r.qty)
        self.table.setCellWidget(i, 3, r.unit)
        self.table.setCellWidget(i, 4, r.price)
        self.table.setCellWidget(i, 5, r.total)
        self.table.setCellWidget(i, 6, W.icon_button("trash", "حذف البند", lambda rr=r: self._delete(rr), "danger"))
        self.rows.append(r)
        return r

    def add_row(self) -> None:
        if not self.main.isVisible():
            return
        if self.rows and self.rows[-1].line().is_blank:
            r = self.rows[-1]
        else:
            r = self._append(Line(""))
        self.table.scrollToBottom()
        r.item.setFocus()

    def _delete(self, r: _Row) -> None:
        i = self.rows.index(r)
        self.rows.pop(i)
        self.table.removeRow(i)
        for n in range(self.table.rowCount()):
            w = self.table.cellWidget(n, 0)
            if isinstance(w, QLabel):
                w.setText(str(n + 1))
        if not self.rows:
            self._append(Line(""))
        self.changed()

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: N802
        if ev.type() == QEvent.Type.KeyPress and ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            for r in self.rows:
                if obj in (r.price, r.total) and r is self.rows[-1]:
                    self.add_row()
                    return True
                if obj in (r.item, r.item.lineEdit(), r.qty, r.unit, r.price, r.total):
                    if obj in (r.item, r.item.lineEdit()) and r.item.completer().popup().isVisible():
                        return False
                    self.focusNextChild()
                    return True
        return super().eventFilter(obj, ev)

    # ------------------------------------------------------------ saving
    def changed(self) -> None:
        if self.loading or self.sheet is None:
            return
        self.dirty = True
        self.saved_lb.setText("جارٍ الحفظ…")
        self._update_summary()
        self.timer.start()

    def _collect(self) -> Sheet | None:
        if self.sheet is None:
            return None
        s = self.sheet
        s.received = self.received.value()
        s.wage = self.wage.value()
        s.entry_fee = self.fee.value()
        s.notes = self.notes.toPlainText().strip()
        s.lines = [r.line() for r in self.rows]
        return s

    def save(self) -> None:
        self.timer.stop()
        if not self.dirty or self.sheet is None:
            return
        s = self._collect()
        if s is None:
            return
        lines = s.lines
        self.repo.save_sheet(s)
        s.lines = lines
        self.dirty = False
        self.saved_lb.setText("تم الحفظ")
        i = self.rest_ids.index(s.restaurant_id) if s.restaurant_id in self.rest_ids else -1
        if i >= 0:
            self.tabs.setTabText(i, self._tab_text(s.restaurant_id, self.rest_names[s.restaurant_id]))
        self._refresh_items()
        self.state.dataChanged.emit()

    def _refresh_items(self) -> None:
        names = [i.name for i in self.repo.items()]
        if names != self.item_names:
            self.item_names = names
            for r in self.rows:
                cur = r.item.currentText()
                r.item.blockSignals(True)
                r.item.clear()
                r.item.addItems(names)
                r.item.setCurrentIndex(-1)
                r.item.setEditText(cur)
                r.item.blockSignals(False)
                r.item.completer().model().setStringList(names)  # type: ignore[attr-defined]

    def leave(self) -> bool:
        self.save()
        return True

    # ------------------------------------------------------------ summary
    def _update_summary(self) -> None:
        s = self._collect()
        if s is None:
            return
        real = [ln for ln in s.lines if not ln.is_blank]
        p = ledger.purchases(real)
        self.sum_count.setText(f"المشتريات ({len(real)} صنف)")
        self.sum_lines.setText(W.money_text(p))
        self.sum_fixed.setText(W.money_text(s.wage + s.entry_fee))
        self.sum_total.setText(W.money_text(p + s.wage + s.entry_fee))
        rem = s.received - (p + s.wage + s.entry_fee)
        self.remain.setText(fmt(rem))
        neg = rem < 0
        W.set_role(self.remain, "bigBad" if neg else "big")
        self.remain_box.setStyleSheet(
            f"#remainBox {{ background: {theme.t('surface_alert' if neg else 'surface_tint')}; border-radius: 14px; }}")
        self.remain_cap.setText("⚠ المصروف أكبر من المستلم" if neg else "المتبقي")
        W.clear_layout(self.badge_host)
        tmp = Sheet(s.day, s.restaurant_id, received=s.received, wage=s.wage, entry_fee=s.entry_fee,
                    done=s.done, lines=real)
        self.badge_host.addWidget(W.state_badge(ledger.sheet_state(tmp).value))
        self.done_btn.setText("إعادة فتح" if s.done else "تم الشراء")

    def _toggle_done(self) -> None:
        if self.sheet is None:
            return
        self.sheet.done = not self.sheet.done
        self.dirty = True
        self.save()
        self._update_summary()

    def _print(self) -> None:
        if self.sheet is None or not self.main.isVisible():
            return
        self.save()
        s = self.repo.sheet(self.state.day_iso, self.sheet.restaurant_id)
        printing.preview(self, printing.sheet_html(s, self.rest_names[s.restaurant_id]))

    def _pdf(self) -> None:
        if self.sheet is None or not self.main.isVisible():
            return
        self.save()
        s = self.repo.sheet(self.state.day_iso, self.sheet.restaurant_id)
        name = self.rest_names[s.restaurant_id]
        printing.save_pdf(self, printing.sheet_html(s, name), f"{s.day} - {name}.pdf")
