"""Two small painted charts: daily expense columns and a share bar."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from talabiya.core.money import fmt
from talabiya.gui import theme


class ColumnChart(QWidget):
    """Columns laid out right-to-left (oldest on the right, as Arabic reads). Last column highlighted."""

    def __init__(self) -> None:
        super().__init__()
        self.data: list[tuple[str, int]] = []
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self.data = data
        self.setToolTip("\n".join(f"{lbl}: {fmt(v)} د.ل" for lbl, v in data))
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        if not self.data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        top, bottom = 24, 28
        n = len(self.data)
        gap = 12
        col_w = min(56.0, (w - gap * (n + 1)) / n)
        total_w = n * col_w + (n - 1) * gap
        x0 = (w + total_w) / 2           # right edge
        mx = max(v for _, v in self.data) or 1
        num_font = QFont(theme.FONT_NUM, 9)
        num_font.setBold(True)
        lbl_font = QFont(theme.FONT_BODY, 9)
        lbl_font.setBold(True)
        base = h - bottom
        for i, (lbl, v) in enumerate(self.data):
            right = x0 - i * (col_w + gap)
            left = right - col_w
            bh = (base - top) * v / mx
            color = QColor(theme.t("green") if i == n - 1 else theme.t("brand"))
            if v == 0:
                color = QColor(theme.t("divider"))
                bh = 3
            path = QPainterPath()
            path.addRoundedRect(QRectF(left, base - bh, col_w, bh), 6, 6)
            p.fillPath(path, color)
            p.setPen(QColor(theme.t("ink")))
            p.setFont(num_font)
            p.drawText(QRectF(left - 10, base - bh - 20, col_w + 20, 18), Qt.AlignmentFlag.AlignCenter,
                       f"{round(v / 1000):,}")
            p.setPen(QColor(theme.t("ink_muted")))
            p.setFont(lbl_font)
            p.drawText(QRectF(left - 10, base + 4, col_w + 20, 22), Qt.AlignmentFlag.AlignCenter, lbl)
        p.end()


class ShareBar(QWidget):
    COLORS = ["brand", "green", "gold", "control_border", "tomato", "ink_muted"]

    def __init__(self) -> None:
        super().__init__()
        self.values: list[int] = []
        self.setFixedHeight(18)

    def set_values(self, values: list[int]) -> None:
        self.values = values
        self.update()

    @classmethod
    def color(cls, i: int) -> str:
        return theme.t(cls.COLORS[i % len(cls.COLORS)])

    def paintEvent(self, _e) -> None:  # noqa: N802
        total = sum(self.values)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 9, 9)
        p.setClipPath(clip)
        p.fillRect(self.rect(), QColor(theme.t("surface_tint")))
        if total:
            x = float(self.width())
            for i, v in enumerate(self.values):
                seg = self.width() * v / total
                p.fillRect(QRectF(x - seg, 0, seg, self.height()), QColor(self.color(i)))
                x -= seg
        p.end()


class ProgressBar(QWidget):
    """Spent share of received, filling from the right."""

    def __init__(self, ratio: float) -> None:
        super().__init__()
        self.ratio = ratio
        self.setFixedHeight(10)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        bg = QPainterPath()
        bg.addRoundedRect(r, 5, 5)
        p.fillPath(bg, QColor(theme.t("surface_tint")))
        f = min(1.0, max(0.0, self.ratio))
        if f > 0:
            fg = QPainterPath()
            fg.addRoundedRect(QRectF(self.width() * (1 - f), 0, self.width() * f, self.height()), 5, 5)
            p.fillPath(fg, QColor(theme.t("danger") if self.ratio > 1 else theme.t("brand")))
        p.end()
