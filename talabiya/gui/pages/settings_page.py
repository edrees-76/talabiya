"""Settings: scheduled backup (frequency + folder), backup now / restore, password and secret question."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from talabiya.core import auth, backup
from talabiya.core.repo import RepoError
from talabiya.gui import widgets as W
from talabiya.gui.auth_dialogs import _password, _question_combo
from talabiya.gui.state import Page


class SettingsPage(Page):
    title = "الإعدادات"
    subtitle = "النسخ الاحتياطي وكلمة السر"

    def __init__(self, state) -> None:
        super().__init__(state)
        self.restore_handler = None   # set by the app: callable(Path) -> None
        row = QHBoxLayout()
        row.setSpacing(20)

        bk = W.Card("النسخ الاحتياطي", "save")
        bk.lay.addWidget(W.label("التكرار", "label"))
        self.freq = QComboBox()
        for k, v in backup.FREQUENCIES.items():
            self.freq.addItem(v, k)
        self.freq.currentIndexChanged.connect(
            lambda _i: self.repo.set_setting("backup_frequency", self.freq.currentData()))
        bk.lay.addWidget(self.freq)
        bk.lay.addWidget(W.label("مجلد النسخ", "label"))
        fr = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText("لم يُختر مجلد بعد")
        fr.addWidget(self.folder, 1)
        fr.addWidget(W.button("اختيار…", icon="folder", on_click=self._choose))
        bk.lay.addLayout(fr)
        self.status_host = QVBoxLayout()
        bk.lay.addLayout(self.status_host)
        acts = QHBoxLayout()
        acts.addWidget(W.button("نسخ الآن", "primary", "save", on_click=self._backup_now))
        acts.addWidget(W.button("استرجاع نسخة…", icon="restore", on_click=self._restore))
        acts.addStretch(1)
        bk.lay.addLayout(acts)
        bk.lay.addWidget(W.label(f"قاعدة البيانات: {state.db_path}", "muted", wrap=True))
        bk.lay.addStretch(1)
        row.addWidget(bk, 1)

        pw = W.Card("كلمة السر", "lock")
        self.cur = _password()
        self.new1 = _password()
        self.new2 = _password()
        for cap, w in (("كلمة السر الحالية", self.cur), ("كلمة السر الجديدة", self.new1),
                       ("أعد كتابة الجديدة", self.new2)):
            pw.lay.addWidget(W.label(cap, "label"))
            pw.lay.addWidget(w)
        pw.lay.addWidget(W.button("تغيير كلمة السر", "primary", on_click=self._change_pw), 0)
        pw.lay.addWidget(W.hline())
        pw.lay.addWidget(W.label("السؤال السري", "label"))
        self.q = _question_combo()
        pw.lay.addWidget(self.q)
        pw.lay.addWidget(W.label("الإجابة الجديدة", "label"))
        self.a = QLineEdit()
        pw.lay.addWidget(self.a)
        pw.lay.addWidget(W.label("يتطلب كتابة كلمة السر الحالية في الأعلى", "muted"))
        pw.lay.addWidget(W.button("حفظ السؤال السري", on_click=self._change_q))
        pw.lay.addStretch(1)
        row.addWidget(pw, 1)
        self.body.addLayout(row)
        self.body.addStretch(1)

    def refresh(self) -> None:
        self.freq.blockSignals(True)
        self.freq.setCurrentIndex(self.freq.findData(backup.frequency(self.repo)))
        self.freq.blockSignals(False)
        f = backup.folder(self.repo)
        self.folder.setText(str(f) if f else "")
        self.q.setEditText(auth.secret_question(self.repo))
        self._status()

    def _status(self) -> None:
        W.clear_layout(self.status_host)
        last = backup.last_backup(self.repo)
        f = backup.folder(self.repo)
        if f is None:
            self.status_host.addWidget(W.Alert("warn", "alert", "اختر مجلداً ليبدأ النسخ التلقائي"))
        elif last is None:
            self.status_host.addWidget(W.Alert("warn", "clock", "لم تُؤخذ أي نسخة بعد"))
        else:
            n = len(backup.list_backups(f))
            self.status_host.addWidget(W.Alert("ok", "check", f"آخر نسخة: {last.strftime('%Y-%m-%d %H:%M')} — "
                                                              f"في المجلد {n} نسخة"))

    def _choose(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "اختر مجلد النسخ الاحتياطية", self.folder.text())
        if d:
            self.repo.set_setting("backup_folder", d)
            self.refresh()

    def _backup_now(self) -> None:
        f = backup.folder(self.repo)
        if f is None:
            W.error(self, "اختر مجلد النسخ أولاً")
            return
        try:
            path = backup.make_backup(self.repo, f)
        except RepoError as e:
            W.error(self, str(e))
            return
        W.info(self, f"حُفظت النسخة:\n{path}")
        self._status()

    def _restore(self) -> None:
        start = str(backup.folder(self.repo) or "")
        path, _ = QFileDialog.getOpenFileName(self, "اختر النسخة المراد استرجاعها", start,
                                              "نسخ طلبية (*.db);;كل الملفات (*)")
        if not path:
            return
        if not W.confirm(self, "ستُستبدل كل البيانات الحالية بمحتوى هذه النسخة (تُحفظ البيانات الحالية جانباً "
                               "باسم before-restore). هل تريد الاسترجاع؟", "استرجاع", danger=True):
            return
        if self.restore_handler:
            self.restore_handler(Path(path))

    def _change_pw(self) -> None:
        if self.new1.text() != self.new2.text():
            W.error(self, "كلمتا السر الجديدتان غير متطابقتين")
            return
        try:
            auth.change_password(self.repo, self.cur.text(), self.new1.text())
        except RepoError as e:
            W.error(self, str(e))
            return
        for e in (self.cur, self.new1, self.new2):
            e.clear()
        W.info(self, "تم تغيير كلمة السر")

    def _change_q(self) -> None:
        try:
            auth.change_secret(self.repo, self.cur.text(), self.q.currentText(), self.a.text())
        except RepoError as e:
            W.error(self, str(e))
            return
        self.cur.clear()
        self.a.clear()
        W.info(self, "حُفظ السؤال السري")
