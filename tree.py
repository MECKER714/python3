#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tree.py - 터미널에서 도는 3D 아스키 크리스마스 트리 (파이썬 표준 라이브러리만 사용)

  실행:  python3 tree.py        종료: Ctrl+C
  권장 터미널 크기: 80x26 이상 (256색 지원 터미널)

  타임라인
    0초   트리 회전 + 눈
    0~3초 금색 전구 줄 / 꼬마전구 / 꼭대기 별이 아래부터 차례로 달림
    5초   산타 썰매가 위쪽을 지나감 (선물은 처음부터 트리 밑에 놓여 있음)
    12초  가장 큰 상자에 이름표가 달리고, 열리면서 MESSAGE가 한 글자씩 나옴

  같은 파일을 GitHub Pages(Pyodide)에서도 그대로 사용합니다. -> render_frame()
"""
import math
import os
import random
import shutil
import sys
import time

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------
MESSAGE = "메리 크리스마스! 올해도 고생 많았어요"   # 상자에서 나오는 문구
TAG = "직원"                                        # 상자 이름표

FPS = 20
RAMP = ".:-=+*#%@"                  # 어두움 -> 밝음
MIN_COLS, MIN_ROWS = 80, 26

T_DECOR = 3.0        # 장식이 아래부터 달리는 시간(초)
T_SLEIGH = 5.0       # 썰매 등장
SLEIGH_DUR = 5.0     # 썰매가 화면을 가로지르는 시간
T_OPEN = 12.0        # 이름표 + 상자 열기 시작
TAG_DUR = 0.6        # 이름표 달리는 시간
OPEN_DELAY = 0.8     # 이름표 후 열리기까지
OPEN_DUR = 1.2       # 뚜껑 열리는 시간
TYPE_SPEED = 0.10    # 글자당 초

GREEN = [22, 22, 28, 34, 34, 40, 46, 82, 118]      # 잎 (RAMP와 같은 길이)
BROWN = [52, 94, 94, 130, 130, 136, 172, 172, 178]  # 기둥

PHI = 0.22                          # 카메라 기울기(위에서 내려다봄)
LIGHT = (-0.45, 0.55, 0.70)         # 빛 방향
SPIN = 0.7                          # 트리 회전 속도(rad/s)

# (중심 x 오프셋, 몸통 너비, 몸통 높이, 몸통색, 리본색)  - 가운데가 가장 큰 상자
GIFTS = [
    (-23, 7, 2, 153, 231),
    (-12, 9, 3, 183, 229),
    (0, 13, 5, 217, 195),
    (13, 9, 3, 223, 153),
    (23, 7, 2, 158, 218),
]
BIG = 2

SLEIGH = [
    "  Y Y    Y Y                   .-==-.   ",
    " ~(o>~~~~(o>~~~~~~~~~~~~~~~~~~/ (@@) \\  ",
    "   /\\     /\\            __.-'_______\\__",
    "  ~~~~~~~~~~~~~~~~~~~~~~~\\___________/  ",
]
SL_W = max(len(s) for s in SLEIGH)
SL_SPLIT = 27        # 이 열부터 썰매(빨강), 앞은 순록
SLEIGH_DROP = 33     # 썰매 배(선물 떨어뜨리는 위치) 열


# ----------------------------------------------------------------------------
# 글자 폭 (한글은 2칸)
# ----------------------------------------------------------------------------
_WIDE = ((0x1100, 0x115F), (0x2E80, 0x303E), (0x3041, 0x33FF), (0x3400, 0x4DBF),
         (0x4E00, 0x9FFF), (0xA960, 0xA97F), (0xAC00, 0xD7A3), (0xF900, 0xFAFF),
         (0xFE30, 0xFE6F), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6))


def cw(ch):
    o = ord(ch)
    if o < 0x1100:
        return 1
    for a, b in _WIDE:
        if a <= o <= b:
            return 2
    return 1


def text_width(s):
    return sum(cw(c) for c in s)


def wrap(text, width):
    lines, cur, cur_w = [], "", 0
    for word in text.split(" "):
        wl = text_width(word)
        add = wl if not cur else wl + 1
        if cur and cur_w + add > width:
            lines.append(cur)
            cur, cur_w = word, wl
        else:
            cur = word if not cur else cur + " " + word
            cur_w += add
    lines.append(cur)
    return lines


# ----------------------------------------------------------------------------
# 캔버스: 셀 = (문자, 전경색, 배경색). 넓은 글자의 둘째 칸은 "" 로 표시
# ----------------------------------------------------------------------------
BLANK = (" ", None, None)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cells = [[BLANK] * w for _ in range(h)]

    def _clear(self, row, i):
        c = row[i][0]
        if c == "":
            if i > 0:
                row[i - 1] = (" ", row[i - 1][1], row[i - 1][2])
        elif cw(c) == 2 and i + 1 < self.w:
            row[i + 1] = (" ", row[i + 1][1], row[i + 1][2])

    def put(self, x, y, ch, fg=None, bg=None):
        if y < 0 or y >= self.h:
            return
        wd = cw(ch)
        if x < 0 or x + wd > self.w:
            return
        row = self.cells[y]
        self._clear(row, x)
        if wd == 2:
            self._clear(row, x + 1)
            row[x] = (ch, fg, bg)
            row[x + 1] = ("", fg, bg)
        else:
            row[x] = (ch, fg, bg)

    def lines(self):
        out = []
        for row in self.cells:
            parts, cur = [], (None, None)
            for ch, fg, bg in row:
                if (fg, bg) != cur:
                    seq = "\x1b[0"
                    if fg is not None:
                        seq += ";38;5;%d" % fg
                    if bg is not None:
                        seq += ";48;5;%d" % bg
                    parts.append(seq + "m")
                    cur = (fg, bg)
                parts.append(ch)
            parts.append("\x1b[0m")
            out.append("".join(parts))
        return out


# ----------------------------------------------------------------------------
# 3D 지오메트리
# ----------------------------------------------------------------------------
def radius(y):
    """높이 y(0~1)에서 트리 반지름. 4단 톱니 모양."""
    u = (y * 4) % 1.0
    base = 0.47 * (1 - 0.80 * y)
    return base * (1 - 0.60 * u)


class Geometry:
    def __init__(self, U):
        rnd = random.Random(1225)
        tau = 2 * math.pi

        self.leaf = []
        ny = max(20, int(U * 2.0))
        for i in range(ny):
            y = i / ny * 0.998
            r = radius(y)
            n = max(8, int(tau * r * U * 2 * 1.6))
            off = rnd.random()
            for j in range(n):
                th = tau * (j + off + (rnd.random() - 0.5) * 0.8) / n
                rr = r * (1 + (rnd.random() - 0.5) * 0.14)
                c, s = math.cos(th), math.sin(th)
                ln = math.sqrt(c * c + 0.64 + s * s)
                self.leaf.append((rr * c, y, rr * s, c / ln, 0.8 / ln, s / ln,
                                  (rnd.random() - 0.5) * 0.30))

        self.trunk = []
        nt = max(6, int(U * 0.9))
        for i in range(nt):
            y = -0.30 + 0.36 * i / nt
            n = max(10, int(tau * 0.075 * U * 2 * 1.8))
            for j in range(n):
                th = tau * (j + rnd.random() * 0.5) / n
                c, s = math.cos(th), math.sin(th)
                self.trunk.append((0.075 * c, y, 0.075 * s, c, 0.0, s,
                                   (rnd.random() - 0.5) * 0.2))

        # 금색 전구 줄 나선 (y 오름차순)
        self.spiral = []
        ns = int(U * 40)
        for k in range(ns):
            s = k / ns
            y = 0.03 + 0.93 * s
            th = tau * 6.0 * s
            r = radius(y) * 1.07 + 0.012
            self.spiral.append((r * math.cos(th), y, r * math.sin(th), k))

        # 빨강 / 파랑 / 분홍 꼬마전구
        self.lights = []
        for _ in range(44):
            y = 0.04 + 0.90 * (1 - math.sqrt(rnd.random()))
            th = rnd.random() * tau
            r = radius(y) * 1.06 + 0.012
            col = rnd.choice((210, 117, 218))
            self.lights.append((r * math.cos(th), y, r * math.sin(th), col,
                                1.0 + rnd.random() * 1.8, rnd.random()))

        # 꼭대기 별 (두 평면을 교차시켜 어느 각도에서도 보이게)
        self.star_cy = 1.06
        self.star = [(0.0, self.star_cy, 0.0)]
        outer, inner = 0.16, 0.05
        for plane in (0, 1):
            for a in range(72):
                phi = tau * a / 72
                m = ((phi - math.pi / 2) % (tau / 5)) / (tau / 5)
                d = abs(1 - 2 * m)
                rb = inner + (outer - inner) * d
                for k in range(1, 6):
                    rr = rb * k / 5
                    px, py = rr * math.cos(phi), rr * math.sin(phi)
                    if plane == 0:
                        self.star.append((px, self.star_cy + py, 0.0))
                    else:
                        self.star.append((0.0, self.star_cy + py, px))


class Snow:
    LAYER_CH = (".", "+", "*")
    LAYER_FG = (240, 247, 255)

    def __init__(self, W, g):
        rnd = random.Random(77)
        self.W, self.g = W, max(g, 1)
        n = max(40, W * self.g // 14)
        self.f = []
        for _ in range(n):
            layer = rnd.choices((0, 1, 2), weights=(5, 3, 2))[0]
            vy = (2.6 + rnd.random() * 1.4, 4.6 + rnd.random() * 2.0,
                  7.2 + rnd.random() * 3.0)[layer]
            self.f.append((layer, rnd.random() * W, rnd.random() * self.g, vy,
                           rnd.random() * 6.283, 0.6 + rnd.random() * 1.6,
                           0.7 + rnd.random() * 1.3, (0.3, 0.7, 1.2)[layer]))

    def at(self, t, layers):
        out = []
        for layer, x0, y0, vy, ph, amp, fq, wind in self.f:
            if layer in layers:
                x = int((x0 + wind * t + amp * math.sin(fq * t + ph)) % self.W)
                y = int((y0 + vy * t) % self.g)
                out.append((x, y, layer))
        return out


# ----------------------------------------------------------------------------
# 장면
# ----------------------------------------------------------------------------
class Scene:
    def __init__(self, message=None):
        self.message = MESSAGE if message is None else message
        self._geo = {}
        self._snow = {}
        self._open = None

    def geometry(self, U):
        key = round(U, 1)
        if key not in self._geo:
            if len(self._geo) > 3:
                self._geo.clear()
            self._geo[key] = Geometry(key)
        return self._geo[key]

    def snow(self, W, g):
        key = (W, g)
        if key not in self._snow:
            self._snow.clear()
            self._snow[key] = Snow(W, g)
        return self._snow[key]

    # ---- 메인 ---------------------------------------------------------------
    def render(self, t, cols, rows):
        W, H = cols - 1, rows - 1
        if cols < MIN_COLS or rows < MIN_ROWS:
            msg = "터미널 크기를 %dx%d 이상으로 키워 주세요 (현재 %dx%d)" % (
                MIN_COLS, MIN_ROWS, cols, rows)
            return "\x1b[H\x1b[2J" + msg

        cv = Canvas(W, H)
        g = H - 2                     # 땅 줄
        cx = W // 2
        U = min((g - 1 - 5) / 1.39, W * 0.30)
        geo = self.geometry(U)
        snow = self.snow(W, g)
        self._open = None

        self._flakes(cv, snow.at(t, (0, 1)), only_empty=True)
        self._tree(cv, t, geo, U, g, cx)
        self._ground(cv, g)
        v = (W + SL_W) / SLEIGH_DUR
        for i in range(len(GIFTS)):
            self._gift(cv, i, t, g, cx, v)
        self._sleigh(cv, t, v)
        self._flakes(cv, snow.at(t, (2,)), only_empty=False)
        self._message(cv, t, W)
        return "\x1b[H" + "\n".join(cv.lines())

    # ---- 눈 -----------------------------------------------------------------
    def _flakes(self, cv, flakes, only_empty):
        for x, y, layer in flakes:
            if only_empty and cv.cells[y][x] != BLANK:
                continue
            cv.put(x, y, Snow.LAYER_CH[layer], Snow.LAYER_FG[layer])

    # ---- 땅 -----------------------------------------------------------------
    def _ground(self, cv, g):
        for x in range(cv.w):
            h = (x * 37 + 11) % 7
            cv.cells[g][x] = (".,:-~'."[h], 255 if h % 2 else 252, None)
            for y in range(g + 1, cv.h):
                if (x + y * 3) % 4 == 0:
                    cv.cells[y][x] = (".", 245, None)

    # ---- 트리 ---------------------------------------------------------------
    def _tree(self, cv, t, geo, U, g, cx):
        W, H = cv.w, cv.h
        a = t * SPIN
        ca, sa = math.cos(a), math.sin(a)
        cp, sp = math.cos(PHI), math.sin(PHI)
        ux = U * 2.0
        yb = -0.30 * cp
        base = g - 1
        zb = [[-9.0] * W for _ in range(H)]
        cells = cv.cells
        Lx, Ly, Lz = LIGHT

        for pts, pal in ((geo.trunk, BROWN), (geo.leaf, GREEN)):
            for x, y, z, nx, ny, nz, bn in pts:
                z1 = -x * sa + z * ca
                zp = y * sp + z1 * cp
                ix = int(cx + (x * ca + z * sa) * ux + 0.5)
                iy = int(base - (y * cp - z1 * sp - yb) * U + 0.5)
                if 0 <= ix < W and 0 <= iy < H and zp > zb[iy][ix]:
                    n1x = nx * ca + nz * sa
                    n1z = -nx * sa + nz * ca
                    d = n1x * Lx + (ny * cp - n1z * sp) * Ly + (ny * sp + n1z * cp) * Lz
                    b = 0.2 + (0.8 * d if d > 0 else 0.0) + bn
                    b *= 0.82 + 0.35 * zp
                    k = int(b * 9)
                    k = 0 if k < 0 else (8 if k > 8 else k)
                    zb[iy][ix] = zp
                    cells[iy][ix] = (RAMP[k], pal[k], None)

        def proj(x, y, z):
            z1 = -x * sa + z * ca
            return (int(cx + (x * ca + z * sa) * ux + 0.5),
                    int(base - (y * cp - z1 * sp - yb) * U + 0.5),
                    y * sp + z1 * cp)

        q = min(1.0, t / T_DECOR)
        yrev = -0.05 + 1.22 * q              # 장식이 달린 높이(아래 -> 위)
        flashing = t < T_DECOR + 0.3

        # 금색 전구 줄
        for x, y, z, k in geo.spiral:
            if y > yrev:
                break
            ix, iy, zp = proj(x, y, z)
            if 0 <= ix < W and 0 <= iy < H and zp + 0.04 > zb[iy][ix]:
                if flashing and yrev - y < 0.05:
                    ch, fg = "@", 231
                else:
                    ch = "o"
                    fg = 231 if math.sin(k * 0.30 - t * 9) > 0.7 else (229 if zp > 0 else 186)
                zb[iy][ix] = zp + 0.04
                cells[iy][ix] = (ch, fg, None)

        # 꼬마전구 깜빡임
        for x, y, z, col, rate, ph in geo.lights:
            if y > yrev:
                continue
            flash = flashing and yrev - y < 0.05
            if not flash and ((t * rate + ph) % 1.0) >= 0.5:
                continue
            ix, iy, zp = proj(x, y, z)
            if 0 <= ix < W and 0 <= iy < H and zp + 0.06 > zb[iy][ix]:
                zb[iy][ix] = zp + 0.06
                cells[iy][ix] = ("O", 231 if flash else col, None)

        # 별
        if yrev >= 1.0:
            fg = 229 if int(t * 6) % 2 else 230
            for i, (x, y, z) in enumerate(geo.star):
                ix, iy, zp = proj(x, y, z)
                if 0 <= ix < W and 0 <= iy < H and zp + 0.10 > zb[iy][ix]:
                    zb[iy][ix] = zp + 0.10
                    cells[iy][ix] = ("@" if i == 0 else "*", 231 if i == 0 else fg, None)
            sx, sy, _ = proj(0.0, geo.star_cy, 0.0)
            if int(t * 4) % 2:
                for dx, dy, ch in ((-6, 0, "-"), (6, 0, "-"), (0, -3, "|"), (0, 3, "|")):
                    cv.put(sx + dx, sy + dy, ch, 230)
            else:
                for dx, dy in ((-5, -2), (5, -2), (-5, 2), (5, 2)):
                    cv.put(sx + dx, sy + dy, "+", 230)

    # ---- 썰매 ---------------------------------------------------------------
    def _sleigh_row(self, t):
        return 1 + int(round(0.8 + 0.8 * math.sin(t * 2.2)))

    def _sleigh(self, cv, t, v):
        if t < T_SLEIGH:
            return
        xl = int(-SL_W + v * (t - T_SLEIGH))
        if xl > cv.w:
            return
        row = self._sleigh_row(t)
        for r, line in enumerate(SLEIGH):
            for c, ch in enumerate(line):
                if ch == " ":
                    continue
                if c < SL_SPLIT:
                    fg = 180 if ch == "Y" else (229 if ch == "~" else (217 if ch == ">" else 223))
                else:
                    fg = 224 if ch == "@" else (231 if ch in ".-=" and r == 0 else 217)
                cv.put(xl + c, row + r, ch, fg)
        rnd = random.Random(int(t * 12))
        for k in range(1, 12):
            if rnd.random() < 1 - k / 12:
                cv.put(xl - k, row + 1 + rnd.randint(0, 2), rnd.choice("*+."),
                       rnd.choice((229, 231, 218, 153)))

    # ---- 선물 ---------------------------------------------------------------
    def _gift(self, cv, i, t, g, cx, v):
        off, bw, bh, body, rib = GIFTS[i]
        gx = cx + off
        total_h = bh + 2
        rb = g - 1                                  # 몸통 맨 아랫줄
        left = gx - bw // 2
        lid_row = rb - bh
        body_top = lid_row + 1
        is_big = i == BIG

        p = 0.0
        if is_big and t >= T_OPEN + OPEN_DELAY:
            p = min(1.0, (t - T_OPEN - OPEN_DELAY) / OPEN_DUR)
            p = 1 - (1 - p) ** 2

        rcols = {bw // 2} if bw < 11 else {bw // 2 - 1, bw // 2, bw // 2 + 1}
        mid = bh // 2
        for r in range(bh):
            for c in range(bw):
                cv.put(left + c, body_top + r, " ", None,
                       rib if (c in rcols or r == mid) else body)

        lift = int(round(3 * p))
        dx = int(round(3 * p))
        ly = lid_row - lift
        if p > 0:                                   # 열린 입구(빛)
            for c in range(-1, bw + 1):
                cv.put(left + c, lid_row, ":" if (c + int(t * 8)) % 2 else " ", 229, 60)
        for c in range(-1, bw + 1):                 # 뚜껑
            inr = c in rcols
            cv.put(left + c + dx, ly, " " if inr else "=", 231, rib if inr else body)
        for k, ch in enumerate("\\@/"):             # 리본 매듭
            cv.put(gx - 1 + k + dx, ly - 1, ch, rib)

        if is_big:
            if t >= T_OPEN:                         # 이름표
                pt = min(1.0, (t - T_OPEN) / TAG_DUR)
                e = 1 - (1 - pt) ** 2
                dy = int(round((1 - e) * 6))
                s = "[" + TAG + "]"
                x = gx - text_width(s) // 2
                for ch in s:
                    cv.put(x, rb - 1 - dy, ch, 95, 230)
                    x += cw(ch)
            self._open = (gx, lid_row, p)

    # ---- 메시지 -------------------------------------------------------------
    def _message(self, cv, t, W):
        if not self._open or self._open[2] <= 0:
            return
        gx, lid_row, p = self._open
        lines = wrap(self.message, max(10, W - 12))
        L = len(lines)
        dw = max(text_width(s) for s in lines)
        bw = dw + 4
        bx = max(0, min(W - bw, gx - bw // 2))
        box_bottom = max(L + 1, lid_row - 6)
        box_top = box_bottom - L - 1

        # 빛줄기
        reach = int(p * (lid_row - box_bottom - 1))
        for k in range(-3, 4):
            for n in range(1, reach + 1):
                yy = lid_row - n
                col = gx + int(k * (1 + n * 0.25))
                cv.put(col, yy, "|" if k % 2 == 0 else ":",
                       229 if (yy + int(t * 12) + k) % 3 else 230)

        if p < 0.7:
            return
        for y in range(box_top, box_bottom + 1):
            for x in range(bx, bx + bw):
                cv.put(x, y, " ", None, 224)
        cv.put(bx, box_top, "*", 217, 224)
        cv.put(bx + bw - 1, box_top, "*", 217, 224)
        cv.put(bx, box_bottom, "*", 217, 224)
        cv.put(bx + bw - 1, box_bottom, "*", 217, 224)

        chars = []
        for li, line in enumerate(lines):
            x = bx + 2 + (dw - text_width(line)) // 2
            for ch in line:
                chars.append((x, box_top + 1 + li, ch))
                x += cw(ch)

        t_type0 = T_OPEN + OPEN_DELAY + OPEN_DUR
        cnt = 0 if t < t_type0 else int((t - t_type0) / TYPE_SPEED) + 1
        for x, y, ch in chars[:cnt]:
            cv.put(x, y, ch, 95, 224)
        if cnt < len(chars):                       # 커서
            x, y, _ = chars[cnt]
            if int(t * 4) % 2 == 0 or cnt > 0:
                cv.put(x, y, "_", 175, 224)
        else:                                      # 다 나온 뒤 반짝이
            rnd = random.Random(int(t * 8))
            for _ in range(10):
                sx = rnd.randint(bx - 4, bx + bw + 3)
                sy = rnd.randint(box_top - 2, lid_row - 2)
                inside = 0 <= sy < cv.h and 0 <= sx < cv.w
                if inside and cv.cells[sy][sx] == BLANK:
                    cv.put(sx, sy, rnd.choice("*+."), rnd.choice((229, 231, 218, 153)))


# ----------------------------------------------------------------------------
# 외부에서 쓰는 진입점 (웹/Pyodide 용) 과 터미널 실행
# ----------------------------------------------------------------------------
_scene = None


def render_frame(t, cols, rows):
    """t초 시점의 화면을 ANSI 문자열로 반환."""
    global _scene
    if _scene is None:
        _scene = Scene()
    return _scene.render(t, cols, rows)


def main():
    if os.name == "nt":
        os.system("")                              # Windows에서 ANSI 활성화
    out = sys.stdout
    scene = Scene()
    out.write("\x1b[?1049h\x1b[?25l\x1b[2J")
    out.flush()
    t0 = time.perf_counter()
    frame = 0
    last = None
    try:
        while True:
            t = time.perf_counter() - t0
            size = shutil.get_terminal_size((100, 32))
            if (size.columns, size.lines) != last:
                out.write("\x1b[2J")
                last = (size.columns, size.lines)
            out.write(scene.render(t, size.columns, size.lines))
            out.flush()
            frame += 1
            delay = t0 + frame / FPS - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:                                  # 느리면 프레임을 건너뜀
                frame = int((time.perf_counter() - t0) * FPS) + 1
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        out.flush()
    print("메리 크리스마스! 🎄" if os.name != "nt" else "Merry Christmas!")


if __name__ == "__main__":
    main()
