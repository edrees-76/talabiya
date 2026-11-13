"""Restaurants: add, rename, order, pause, delete (only without purchases)."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from talabiya.core.repo import RepoError
from talabiya.gui import widgets as W
from talabiya.gui.state import Page


class RestaurantDialog(QDialog):
    def __init__(self, parent: QWidget, name: str = "", note: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("تعديل مطعم" if name else "إضافة مطعم")
        self.setFixedWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)
        lay.addWidget(W.label(self.windowTitle(), "h3"))
        lay.addWidget(W.label("اسم المطعم", "label"))
        self.name = QLineEdit(name)
        self.name.setPlaceholderText("مثال: مطعم العاصمة")
        lay.addWidget(self.name)
        lay.addWidget(W.label("ملاحظة (اختياري)", "label"))
        self.note = QLineEdit(note)
        self.note.setPlaceholderText("الفرع أو العنوان أو رقم الهاتف")
        lay.addWidget(self.note)
        self.err = W.label("", "up", wrap=True)
        lay.addWidget(self.err)
        row = QHBoxLayout()
        row.addWidget(W.button("حفظ" if name else "إضافة", "fresh", "check" if name else "plus", on_click=self._ok))
        row.addWidget(W.button("إلغاء", on_click=self.reject))
        row.addStretch(1)
        lay.addLayout(row)
        self.name.returnPressed.connect(self._ok)
        self.on_save = None

    def _ok(self) -> None:
        try:
            if self.on_save:
                self.on_save(self.name.text(), self.note.text())
        except RepoError as e:
            self.err.setText(str(e))
            return
        self.accept()


class RestaurantsPage(Page):
    title = "المطاعم"
    subtitle = "المطاعم التي تشتري لها"

    def __init__(self, state) -> None:
        super().__init__(state)
        self.top_actions.addWidget(W.button("إضافة مطعم", "fresh", "plus", on_click=self._add))
        self.card = W.Card()
        self.list_host = QVBoxLayout()
        self.list_host.setSpacing(0)
        self.card.lay.addLayout(self.list_host)
        self.body.addWidget(self.card)
        self.body.addStretch(1)

    def refresh(self) -> None:
        W.clear_layout(self.list_host)
        rests = self.repo.restaurants(include_inactive=True)
        if not rests:
            self.list_host.addWidget(W.label("لا توجد مطاعم بعد. اضغط «إضافة مطعم» لإضافة أول مطعم.", "muted"))
            return
        today = date.today()
        m0 = today.replace(day=1)
        m1 = (m0 + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        month = dict(self.repo.month_by_restaurant(m0, m1))
        for i, r in enumerate(rests):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 10, 0, 10)
            rl.setSpacing(12)
            rl.addWidget(W.label(str(i + 1), "muted"))
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(W.label(r.name, "h2"))
            if r.note:
                col.addWidget(W.label(r.note, "muted"))
            rl.addLayout(col, 1)
            rl.addWidget(W.label(f"مشتريات الشهر  {W.money_text(month.get(r.name, 0))}", "muted"))
            rl.addWidget(W.Badge("done", "نشط", "check") if r.active else W.Badge("new", "موقوف", "pause"))
            rl.addWidget(W.icon_button("chevron_up", "تحريك لأعلى", lambda rid=r.id: self._move(rid, -1), "brand"))
            rl.addWidget(W.icon_button("chevron_down", "تحريك لأسفل", lambda rid=r.id: self._move(rid, 1), "brand"))
            rl.addWidget(W.button("تعديل", small=True, icon="edit", on_click=lambda rr=r: self._edit(rr)))
            if r.active:
                rl.addWidget(W.button("إيقاف", small=True, icon="pause", on_click=lambda rr=r: self._toggle(rr),
                                      tip="يخفيه من شاشة المشتريات دون حذف سجله"))
            else:
                rl.addWidget(W.button("تفعيل", small=True, icon="play", on_click=lambda rr=r: self._toggle(rr)))
            rl.addWidget(W.icon_button("trash", "حذف المطعم", lambda rr=r: self._delete(rr), "danger"))
            self.list_host.addWidget(row)
            if i < len(rests) - 1:
                self.list_host.addWidget(W.hline())

    def _changed(self) -> None:
        self.state.dataChanged.emit()
        self.refresh()

    def _add(self) -> None:
        d = RestaurantDialog(self)
        d.on_save = lambda n, note: self.repo.add_restaurant(n, note)
        if d.exec():
            self._changed()

    def _edit(self, r) -> None:
        d = RestaurantDialog(self, r.name, r.note)
        d.on_save = lambda n, note: self.repo.update_restaurant(r.id, n, note)
        if d.exec():
            self._changed()

    def _toggle(self, r) -> None:
        self.repo.set_restaurant_active(r.id, not r.active)
        self._changed()

    def _move(self, rid: int, step: int) -> None:
        self.repo.move_restaurant(rid, step)
        self._changed()

    def _delete(self, r) -> None:
        if self.repo.restaurant_has_sheets(r.id):
            W.error(self, "لهذا المطعم مشتريات مسجلة فلا يمكن حذفه. استخدم «إيقاف» ليختفي من شاشة المشتريات "
                          "مع بقاء سجله")
            return
        if W.confirm(self, f"حذف المطعم «{r.name}»؟", "حذف", danger=True):
            self.repo.delete_restaurant(r.id)
            self._changed()
