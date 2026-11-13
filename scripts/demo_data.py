"""Fill a database with fictional restaurants and ~2 weeks of purchases (for screenshots and trying the UI).

    python scripts/demo_data.py <path-to.db>
Never run it on the real database: it refuses a file that already has restaurants.
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from talabiya.core import auth  # noqa: E402
from talabiya.core.db import connect  # noqa: E402
from talabiya.core.models import Line, Sheet  # noqa: E402
from talabiya.core.money import to_millis  # noqa: E402
from talabiya.core.repo import Repo  # noqa: E402
from talabiya.core.seed import ITEMS, UNITS  # noqa: E402

RESTAURANTS = ["مطعم الواحة", "مطعم السرايا", "مطعم البحر", "مطعم الريف"]
BASKET = [("سلاطة", "قابية", 30), ("طماطم", "كجم", 3.5), ("هريسة", "كجم", 7), ("فلفل حلو", "كجم", 5),
          ("فلفل حار", "كجم", 5), ("ليم", "كجم", 5), ("بصل حويل", "كجم", 5), ("كسبر", "شك", 3),
          ("زيت عباد الشمس", "صندوق", 150), ("مقسم وجبات", "صندوق", 90), ("جبنة شرائح", "صندوق", 160),
          ("ارز", "شوال", 140), ("جبنة موزريلا", "قطعة", 92.5), ("دقيق", "شوال", 205), ("مناديل", "كيس", 24),
          ("شكاير زبون سوداء", "استيكة", 15), ("حليب", "باكو", 7.5), ("خميرة", "باكو", 14.5)]


def fill(path: Path, today: date, days: int = 14, password: str = "1234") -> None:
    conn = connect(path)
    repo = Repo(conn)
    if repo.restaurants(include_inactive=True):
        raise SystemExit("قاعدة البيانات فيها مطاعم: لن تُضاف بيانات تجريبية")
    repo.seed_catalog(UNITS, ITEMS)
    if not auth.is_configured(repo):
        auth.setup(repo, password, "ما اسم أول مدرسة درست فيها؟", "الأمل")
    ids = [repo.add_restaurant(n) for n in RESTAURANTS]
    rnd = random.Random(7)
    for k in range(days, -1, -1):
        d = today - timedelta(days=k)
        for j, rid in enumerate(ids):
            if k == 0 and j == 1:
                continue                      # one restaurant not started today
            lines = []
            for name, unit, price in rnd.sample(BASKET, rnd.randint(4, 9)):
                p = price * rnd.choice([1, 1, 1, 0.9, 1.1, 1.12])
                lines.append(Line(name, Decimal(rnd.choice([1, 2, 2, 3, 5, 10])), unit, to_millis(round(p, 2))))
            spent = sum(ln.total for ln in lines) + 53_000
            received = (spent // 100_000 + 1) * 100_000 + rnd.choice([0, 100_000])
            repo.save_sheet(Sheet(d.isoformat(), rid, received=received, wage=50_000, entry_fee=3_000,
                                  done=k > 0, lines=lines))
        if k > 1:
            ret = sum(s.received - (sum(ln.total for ln in s.lines) + s.wage + s.entry_fee)
                      for s in repo.sheets_for_day(d.isoformat()))
            repo.close_day(d.isoformat(), ret - rnd.choice([0, 0, 0, 5_000, -2_500]))
    conn.close()


if __name__ == "__main__":
    fill(Path(sys.argv[1]), date.today())
    print("تمت إضافة البيانات التجريبية")
