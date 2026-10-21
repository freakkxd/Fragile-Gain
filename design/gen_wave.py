#!/usr/bin/env python3
"""Fragile Gain: звуковая «огибающая» — знак приложения.

Чёрная область — |y| < A(x): ряд острых шатров разной высоты (несимметричный
ритм) с тонкой перемычкой между двумя главными пиками.

Использование:
  python3 design/gen_wave.py out.svg                  # иконка на светлой плитке (палитра Fragile Notes)
  python3 design/gen_wave.py out.svg --tray "#ffffff" # знак без фона для трея: прозрачный холст, заданный цвет
"""
import sys
import numpy as np

args = [a for a in sys.argv[1:]]
TRAY = "--tray" in args
if TRAY:
    i = args.index("--tray")
    COLOR = args[i + 1]
    del args[i:i + 2]
else:
    COLOR = "#18181b"
OUT = args[0] if args else "wave.svg"

# пики: (положение -1…1, высота, ширина основания, скругление вершины).
# Два главных пика с перемычкой, малые по бокам и «рожки» у краёв; высоты
# разные слева и справа.
PEAKS = [
    (-1.00, 56, 0.090, 0.020),
    (-0.67, 72, 0.190, 0.040),
    (-0.234, 168, 0.198, 0.050),
    (0.234, 236, 0.198, 0.050),
    (0.67, 132, 0.190, 0.040),
    (1.00, 96, 0.090, 0.020),
]

# Иконка: знак 620 px на плитке 1024. Трей: знак почти во весь холст, выше по
# вертикали и с толстой перемычкой — иначе в 16–24 px он превращается в пятно.
W = 960.0 if TRAY else 620.0
VSCALE = 1.28 if TRAY else 1.0
NECK = 15.0 if TRAY else 4.0


def tent(x, c, h, w, r):
    d = np.sqrt((x - c) ** 2 + r * r) - r
    return h * np.clip(1 - d / w, 0, None)


def amp(x):
    t = np.clip(np.abs(x) / 0.30, 0, 1)
    parts = [NECK + 30 * (t * t * (3 - 2 * t))]              # перемычка в центре, ровные «долины»
    parts += [tent(x, c, h, w, r) for c, h, w, r in PEAKS]
    P = 4.0
    return sum(np.maximum(p, 0) ** P for p in parts) ** (1 / P)


xs = np.linspace(-1, 1, 721)
A = amp(xs) * (W / 640.0) * VSCALE
px = 512 + xs * (W / 2)
top = [(px[i], 512 - A[i]) for i in range(len(xs))]
bot = [(px[i], 512 + A[i]) for i in range(len(xs) - 1, -1, -1)]
d = "M" + " L".join("%.1f %.1f" % p for p in top + bot) + "Z"

if TRAY:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <title>Fragile Gain</title>
  <!-- Tray mark: no background, single flat colour. -->
  <path d="{d}" fill="{COLOR}" stroke="{COLOR}" stroke-width="2" stroke-linejoin="round"/>
</svg>
'''
else:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <title>Fragile Gain</title>
  <!-- Sound envelope. Mono light tile, zinc palette (as Fragile Notes). -->
  <rect x="8" y="8" width="1008" height="1008" rx="224" fill="#f4f4f5" stroke="#d4d4d8" stroke-width="8"/>
  <path d="{d}" fill="{COLOR}" stroke="{COLOR}" stroke-width="2" stroke-linejoin="round"/>
</svg>
'''
open(OUT, "w").write(svg)
print("bytes", len(svg))
