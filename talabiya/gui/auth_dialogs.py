"""First-run setup, login and password recovery."""
from __future__ import annotations

import math
import time
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from talabiya.core import auth, backup
from talabiya.core.repo import Repo, RepoError
from talabiya.core.seed import DEFAULT_QUESTIONS, GROUPS, UNITS
from talabiya.gui import widgets as W


def _field(lay: QVBoxLayout, caption: str, w: QWidget, hint: str | None = None) -> QWidget:
    lay.addWidget(W.label(caption, "label"))
    lay.addWidget(w)
    if hint:
        lay.addWidget(W.label(hint, "muted", wrap=True))
    return w


def _password() -> QLineEdit:
    e = QLineEdit()
    e.setEchoMode(QLineEdit.EchoMode.Password)
    e.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    return e


def _question_combo(current: str = "") -> QComboBox:
    c = QComboBox()
    c.setEditable(True)
    c.addItems(DEFAULT_QUESTIONS)
    if current:
        c.setEditText(current)
    return c


class SetupDialog(QDialog):
    """First run: password + secret question, review the starting catalogue, backup folder."""

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self.repo = repo
        self.setWindowTitle("الإعداد الأول")
        self.setMinimumSize(640, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(W.logo("logo-horizontal.jpg", 180))
        head.addStretch(1)
        self.step_lb = W.label("", "muted")
        head.addWidget(self.step_lb)
        root.addLayout(head)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.err = W.label("", "up", wrap=True)
        root.addWidget(self.err)
        nav = QHBoxLayout()
        self.next_btn = W.button("التالي", "primary", on_click=self._next)
        self.back_btn = W.button("السابق", on_click=self._back)
        nav.addWidget(self.next_btn)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        root.addLayout(nav)

        # page 1 -- password
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.setSpacing(8)
        l1.addWidget(W.label("مرحباً بك في طلبية", "h3"))
        l1.addWidget(W.label("اختر كلمة سر تُطلب عند فتح البرنامج، وسؤالاً سرياً تسترجع به الدخول إن نسيتها.",
                             "muted", wrap=True))
        self.pw1 = _field(l1, "كلمة السر", _password(), f"{auth.MIN_PASSWORD} خانات على الأقل")
        self.pw2 = _field(l1, "أعد كتابة كلمة السر", _password())
        self.q = _field(l1, "السؤال السري", _question_combo(), "اختر سؤالاً أو اكتب سؤالك")
        self.a = _field(l1, "الإجابة", QLineEdit(), "لا يهم حجم الحروف ولا الهمزات")
        l1.addStretch(1)
        self.stack.addWidget(p1)

        # page 2 -- catalogue
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.addWidget(W.label("راجع قائمة الأصناف والوحدات", "h3"))
        l2.addWidget(W.label("استخرجناها من ملف الإكسل. أزل علامة ما لا تحتاجه، ويمكنك الإضافة لاحقاً من شاشة "
                             "«الأصناف والوحدات» أو أثناء تسجيل المشتريات.", "muted", wrap=True))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self._fill_tree()
        l2.addWidget(self.tree, 1)
        row = QHBoxLayout()
        row.addWidget(W.button("تحديد الكل", small=True, on_click=lambda: self._check_all(True)))
        row.addWidget(W.button("إلغاء تحديد الكل", small=True, on_click=lambda: self._check_all(False)))
        row.addStretch(1)
        self.count_lb = W.label("", "muted")
        row.addWidget(self.count_lb)
        l2.addLayout(row)
        self.tree.itemChanged.connect(lambda *_: self._count())
        self._count()
        self.stack.addWidget(p2)

        # page 3 -- backup
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        l3.setSpacing(8)
        l3.addWidget(W.label("النسخ الاحتياطي", "h3"))
        l3.addWidget(W.label("يحفظ البرنامج نسخة من بياناتك تلقائياً في المجلد الذي تختاره. يُفضّل مجلد على "
                             "OneDrive أو قرص آخر حتى لا تضيع البيانات إن تعطل الجهاز.", "muted", wrap=True))
        self.freq = QComboBox()
        for k, v in backup.FREQUENCIES.items():
            self.freq.addItem(v, k)
        _field(l3, "التكرار", self.freq)
        frow = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText("لم يُختر مجلد بعد")
        frow.addWidget(self.folder, 1)
        frow.addWidget(W.button("اختيار…", icon="folder", on_click=self._choose))
        l3.addWidget(W.label("مجلد النسخ", "label"))
        l3.addLayout(frow)
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self.folder.setText(str(Path(docs) / "طلبية - نسخ احتياطية"))
        l3.addStretch(1)
        self.stack.addWidget(p3)
        self._sync()

    def _fill_tree(self) -> None:
        units = QTreeWidgetItem(self.tree, ["الوحدات"])
        units.setFlags(units.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
        for u in UNITS:
            it = QTreeWidgetItem(units, [u])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked)
            it.setData(0, Qt.ItemDataRole.UserRole, ("unit", u))
        for title, grp in GROUPS:
            g = QTreeWidgetItem(self.tree, [title])
            g.setFlags(g.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
            for name, unit in grp:
                it = QTreeWidgetItem(g, [f"{name}   ({unit})"])
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, Qt.CheckState.Checked)
                it.setData(0, Qt.ItemDataRole.UserRole, ("item", name, unit))

    def _leaves(self):
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            for j in range(g.childCount()):
                yield g.child(j)

    def _check_all(self, on: bool) -> None:
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _count(self) -> None:
        n = sum(1 for it in self._leaves() if it.data(0, Qt.ItemDataRole.UserRole)[0] == "item"
                and it.checkState(0) == Qt.CheckState.Checked)
        self.count_lb.setText(f"{n} صنفاً محدداً")

    def _choose(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "اختر مجلد النسخ الاحتياطية", self.folder.text())
        if d:
            self.folder.setText(d)

    def _sync(self) -> None:
        i = self.stack.currentIndex()
        self.step_lb.setText(f"الخطوة {i + 1} من {self.stack.count()}")
        self.back_btn.setVisible(i > 0)
        self.next_btn.setText("ابدأ استخدام البرنامج" if i == self.stack.count() - 1 else "التالي")
        self.err.setText("")

    def _back(self) -> None:
        self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
        self._sync()

    def _next(self) -> None:
        i = self.stack.currentIndex()
        if i == 0:
            if len(self.pw1.text()) < auth.MIN_PASSWORD:
                self.err.setText(f"أدخل كلمة سر من {auth.MIN_PASSWORD} خانات على الأقل")
                return
            if self.pw1.text() != self.pw2.text():
                self.err.setText("كلمتا السر غير متطابقتين. أعد كتابتهما")
                return
            if not self.q.currentText().strip() or not self.a.text().strip():
                self.err.setText("اكتب السؤال السري وإجابته")
                return
        if i < self.stack.count() - 1:
            self.stack.setCurrentIndex(i + 1)
            self._sync()
            return
        self._finish()

    def _finish(self) -> None:
        try:
            auth.setup(self.repo, self.pw1.text(), self.q.currentText(), self.a.text())
        except RepoError as e:
            self.err.setText(str(e))
            return
        units, items = [], []
        for it in self._leaves():
            if it.checkState(0) != Qt.CheckState.Checked:
                continue
            data = it.data(0, Qt.ItemDataRole.UserRole)
            if data[0] == "unit":
                units.append(data[1])
            else:
                items.append((data[1], data[2]))
        self.repo.seed_catalog(units, items)
        self.repo.set_setting("backup_frequency", self.freq.currentData())
        if self.folder.text().strip():
            self.repo.set_setting("backup_folder", self.folder.text().strip())
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self.repo = repo
        self.fails = 0
        self.locked_until = 0.0   # time.monotonic() before which no attempt is checked
        self.setWindowTitle("تسجيل الدخول")
        self.setFixedWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(12)
        lay.addWidget(W.logo("logo-stacked.jpg", 170))
        h = W.label("تسجيل الدخول", "h3")
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(h)
        lay.addWidget(W.label("كلمة السر", "label"))
        self.pw = _password()
        self.pw.setPlaceholderText("أدخل كلمة السر")
        self.pw.returnPressed.connect(self._login)
        lay.addWidget(self.pw)
        self.err = W.label("", "up", wrap=True)
        lay.addWidget(self.err)
        self.ok = W.button("دخول", "primary", "lock", on_click=self._login)
        lay.addWidget(self.ok)
        forgot = W.button("نسيت كلمة السر؟", "link", on_click=self._recover)
        lay.addWidget(forgot, 0, Qt.AlignmentFlag.AlignCenter)

    def _login(self) -> None:
        left = self.locked_until - time.monotonic()
        if left > 0:
            self.err.setText(f"انتظر {math.ceil(left)} ثانية ثم حاول")
            return
        if auth.check_password(self.repo, self.pw.text()):
            self.accept()
            return
        self.fails += 1
        self.pw.selectAll()
        self.err.setText("كلمة السر غير صحيحة. حاول مرة أخرى")
        if self.fails >= 3:
            wait = min(30, 2 * (self.fails - 2))
            self.locked_until = time.monotonic() + wait
            self.ok.setEnabled(False)
            self.err.setText(f"كلمة السر غير صحيحة. انتظر {wait} ثانية ثم حاول")
            QTimer.singleShot(wait * 1000, lambda: (self.ok.setEnabled(True), self.err.setText("")))

    def _recover(self) -> None:
        if RecoverDialog(self.repo, self).exec():
            W.info(self, "حُفظت كلمة السر الجديدة. ادخل بها الآن")
            self.pw.clear()
            self.pw.setFocus()


class RecoverDialog(QDialog):
    def __init__(self, repo: Repo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("استرجاع كلمة السر")
        self.setFixedWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)
        lay.addWidget(W.label("استرجاع كلمة السر", "h3"))
        lay.addWidget(W.label("السؤال السري:", "label"))
        lay.addWidget(W.label(auth.secret_question(repo), wrap=True))
        self.a = _field(lay, "الإجابة", QLineEdit())
        self.p1 = _field(lay, "كلمة سر جديدة", _password())
        self.p2 = _field(lay, "أعد كتابة كلمة السر الجديدة", _password())
        self.err = W.label("", "up", wrap=True)
        lay.addWidget(self.err)
        row = QHBoxLayout()
        row.addWidget(W.button("حفظ كلمة السر", "primary", on_click=self._save))
        row.addWidget(W.button("إلغاء", on_click=self.reject))
        row.addStretch(1)
        lay.addLayout(row)

    def _save(self) -> None:
        if self.p1.text() != self.p2.text():
            self.err.setText("كلمتا السر غير متطابقتين. أعد كتابتهما")
            return
        try:
            auth.reset_with_answer(self.repo, self.a.text(), self.p1.text())
        except RepoError as e:
            self.err.setText(str(e))
            return
        self.accept()
