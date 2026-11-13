"""Shared catalogue: items (with default unit) and units."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from talabiya.core.repo import RepoError
from talabiya.gui import widgets as W
from talabiya.gui.state import Page


class ItemDialog(QDialog):
    def __init__(self, parent: QWidget, units: list[str], name: str = "", unit: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("تعديل صنف" if name else "صنف جديد")
        self.setFixedWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)
        lay.addWidget(W.label(self.windowTitle(), "h3"))
        lay.addWidget(W.label("اسم الصنف", "label"))
        self.name = QLineEdit(name)
        lay.addWidget(self.name)
        lay.addWidget(W.label("الوحدة الافتراضية", "label"))
        self.unit = QComboBox()
        self.unit.addItem("")
        self.unit.addItems(units)
        self.unit.setCurrentText(unit)
        lay.addWidget(self.unit)
        self.err = W.label("", "up", wrap=True)
        lay.addWidget(self.err)
        row = QHBoxLayout()
        row.addWidget(W.button("حفظ", "fresh", "check", on_click=self._ok))
        row.addWidget(W.button("إلغاء", on_click=self.reject))
        row.addStretch(1)
        lay.addLayout(row)
        self.on_save = None

    def _ok(self) -> None:
        try:
            if self.on_save:
                self.on_save(self.name.text(), self.unit.currentText())
        except RepoError as e:
            self.err.setText(str(e))
            return
        self.accept()


class ItemsPage(Page):
    title = "الأصناف والوحدات"
    subtitle = "قائمة مشتركة لكل المطاعم. الصنف الجديد الذي تكتبه في المشتريات يُضاف هنا تلقائياً"

    def __init__(self, state) -> None:
        super().__init__(state)
        self.top_actions.addWidget(W.button("صنف جديد", "fresh", "plus", on_click=self._add_item))
        row = QHBoxLayout()
        row.setSpacing(20)
        items = W.Card("الأصناف", "list")
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("بحث عن صنف")
        self.search.textChanged.connect(lambda _t: self._fill_items())
        tools.addWidget(self.search, 1)
        self.show_inactive = QCheckBox("إظهار الموقوفة")
        self.show_inactive.toggled.connect(lambda _b: self._fill_items())
        tools.addWidget(self.show_inactive)
        items.lay.addLayout(tools)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["الصنف", "الوحدة الافتراضية", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(60)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 220)
        self.table.setMinimumHeight(520)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._edit_item(self.shown[r]))
        items.lay.addWidget(self.table)
        self.count_lb = W.label("", "muted")
        items.lay.addWidget(self.count_lb)
        row.addWidget(items, 2)

        units = W.Card("الوحدات", "scale")
        self.units = QListWidget()
        self.units.setMinimumHeight(420)
        units.lay.addWidget(self.units)
        ub = QHBoxLayout()
        ub.addWidget(W.button("وحدة جديدة", small=True, icon="plus", on_click=self._add_unit))
        ub.addWidget(W.button("إعادة تسمية", small=True, icon="edit", on_click=self._rename_unit))
        ub.addWidget(W.button("حذف", small=True, icon="trash", on_click=self._delete_unit))
        ub.addStretch(1)
        units.lay.addLayout(ub)
        units.lay.addStretch(1)
        row.addWidget(units, 1)
        self.body.addLayout(row)
        self.body.addStretch(1)

    def refresh(self) -> None:
        self._fill_items()
        self.units.clear()
        self.units.addItems(self.repo.units())

    def _fill_items(self) -> None:
        q = self.search.text().strip()
        all_items = self.repo.items(include_inactive=self.show_inactive.isChecked())
        self.shown = [i for i in all_items if q in i.name]
        self.table.setRowCount(0)
        for r, it in enumerate(self.shown):
            self.table.insertRow(r)
            name = QTableWidgetItem(it.name + ("" if it.active else "  (موقوف)"))
            if not it.active:
                name.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(r, 0, name)
            self.table.setItem(r, 1, QTableWidgetItem(it.default_unit))
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(4, 0, 4, 0)
            lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(W.button("تعديل", small=True, on_click=lambda i=it: self._edit_item(i)))
            lay.addWidget(W.button("إيقاف" if it.active else "تفعيل", small=True,
                                   on_click=lambda i=it: self._toggle(i),
                                   tip="الصنف الموقوف لا يظهر في قائمة الاختيار"))
            lay.addStretch(1)
            self.table.setCellWidget(r, 2, w)
        self.count_lb.setText(f"{len(self.shown)} صنفاً")

    def _add_item(self) -> None:
        d = ItemDialog(self, self.repo.units())
        d.on_save = lambda n, u: self.repo.add_item(n, u)
        if d.exec():
            self._fill_items()

    def _edit_item(self, it) -> None:
        d = ItemDialog(self, self.repo.units(), it.name, it.default_unit)
        d.on_save = lambda n, u: self.repo.update_item(it.id, n, u)
        if d.exec():
            self._fill_items()

    def _toggle(self, it) -> None:
        self.repo.set_item_active(it.id, not it.active)
        self._fill_items()

    def _ask(self, title: str, text: str = "") -> str | None:
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText("اسم الوحدة")
        dlg.setTextValue(text)
        dlg.setOkButtonText("حفظ")
        dlg.setCancelButtonText("إلغاء")
        return dlg.textValue() if dlg.exec() else None

    def _add_unit(self) -> None:
        name = self._ask("وحدة جديدة")
        if name is not None:
            try:
                self.repo.add_unit(name)
            except RepoError as e:
                W.error(self, str(e))
            self.refresh()

    def _rename_unit(self) -> None:
        cur = self.units.currentItem()
        if cur is None:
            W.error(self, "اختر وحدة من القائمة أولاً")
            return
        name = self._ask("إعادة تسمية الوحدة", cur.text())
        if name is not None and name.strip() != cur.text():
            try:
                self.repo.rename_unit(cur.text(), name)
            except RepoError as e:
                W.error(self, str(e))
            self.refresh()

    def _delete_unit(self) -> None:
        cur = self.units.currentItem()
        if cur is None:
            W.error(self, "اختر وحدة من القائمة أولاً")
            return
        if W.confirm(self, f"حذف الوحدة «{cur.text()}»؟", "حذف", danger=True):
            try:
                self.repo.delete_unit(cur.text())
            except RepoError as e:
                W.error(self, str(e))
            self.refresh()
