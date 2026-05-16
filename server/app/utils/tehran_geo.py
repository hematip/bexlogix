"""Tehran district centroids and geographic helpers for realistic seeding.

Coordinates are approximate centroids of Tehran's 22 municipal districts plus
a mapping into the five business regions the application uses
(مرکز / شمال / جنوب / شرق / غرب). They are used by the sample data generator
so stores cluster around plausible streets instead of falling on mountains or
unpopulated areas at the city boundary.
"""

from __future__ import annotations

# (lat, lon) of district centroids inside Tehran's populated area.
TEHRAN_DISTRICT_CENTROIDS: dict[int, tuple[float, float]] = {
    1: (35.793, 51.422),   # تجریش / نیاوران
    2: (35.745, 51.385),   # شهرک غرب
    3: (35.755, 51.420),   # ونک / میرداماد
    4: (35.745, 51.515),   # تهرانپارس / رسالت
    5: (35.745, 51.305),   # پونک
    6: (35.720, 51.405),   # یوسف‌آباد / امیرآباد
    7: (35.722, 51.452),   # مطهری / سهروردی
    8: (35.722, 51.490),   # نارمک
    9: (35.700, 51.345),   # مهرآباد
    10: (35.677, 51.380),  # سینا / هاشمی
    11: (35.687, 51.395),  # امام خمینی
    12: (35.687, 51.430),  # بهارستان
    13: (35.697, 51.482),  # تهران‌نو
    14: (35.667, 51.475),  # بزرگراه محلاتی
    15: (35.640, 51.512),  # افسریه
    16: (35.640, 51.422),  # یخچی‌آباد
    17: (35.652, 51.370),  # ابوذر
    18: (35.640, 51.310),  # یافت‌آباد
    19: (35.610, 51.380),  # خانی‌آباد
    20: (35.580, 51.430),  # شهرری
    21: (35.690, 51.250),  # شهرک وردآورد
    22: (35.760, 51.215),  # چیتگر
}

# Each business region maps to a curated set of districts so that a "north"
# store is genuinely in northern Tehran, not random within the bounding box.
REGION_TO_DISTRICTS: dict[str, list[int]] = {
    "شمال": [1, 2, 3],
    "شرق": [4, 8, 13, 14, 15],
    "جنوب": [16, 17, 18, 19, 20],
    "غرب": [5, 9, 21, 22],
    "مرکز": [6, 7, 10, 11, 12],
}
