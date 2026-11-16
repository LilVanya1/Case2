"""Схема наблюдаемого процесса E2. Запускается из analyze.py."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "схема.png"

W, H = 2480, 1320
BG = (251, 249, 244)
INK = (28, 26, 24)
MUTED = (92, 86, 78)
LINE = (44, 42, 38)
WHITE = (255, 255, 255)
SYS = (235, 232, 224)
OK = (226, 239, 224)
OK_LINE = (47, 107, 61)
BAD = (247, 228, 224)
BAD_LINE = (148, 62, 52)
CAN = (247, 236, 214)
CAN_LINE = (140, 92, 24)
LOOP = (255, 247, 228)
EXTRA = (228, 236, 246)
EXTRA_LINE = (42, 74, 112)


def load_font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path(r"C:\Windows\Fonts") / name
    if not path.exists():
        path = Path(r"C:\Windows\Fonts") / ("arialbd.ttf" if bold else "arial.ttf")
    return ImageFont.truetype(str(path), size)


def rrect(draw, box, fill, outline, width=3, radius=16):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def center_text(draw, box, lines, fonts, fills):
    x0, y0, x1, y1 = box
    steps = [32, 32, 24]
    total = sum(steps[: len(lines)])
    y = y0 + (y1 - y0 - total) / 2
    for line, font, step, color in zip(lines, fonts, steps, fills):
        b = draw.textbbox((0, 0), line, font=font)
        w = b[2] - b[0]
        if w > (x1 - x0 - 24):
            raise SystemExit(f"text overflow: {line}")
        draw.text((x0 + (x1 - x0 - w) / 2, y), line, font=font, fill=color)
        y += step


def stop_before(points, pad=14):
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    end = (x2 - pad * math.cos(ang), y2 - pad * math.sin(ang))
    return points[:-1] + [end]


def arrow(draw, points, fill=LINE, width=3):
    points = stop_before(points)
    draw.line(points, fill=fill, width=width, joint="curve")
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    length = 15
    spread = 2.55
    p1 = (x2 + length * math.cos(ang + spread), y2 + length * math.sin(ang + spread))
    p2 = (x2 + length * math.cos(ang - spread), y2 + length * math.sin(ang - spread))
    draw.polygon([(x2, y2), p1, p2], fill=fill)


def tag(draw, xy, text, font, fill=MUTED):
    x, y = xy
    b = draw.textbbox((0, 0), text, font=font)
    w, h = b[2] - b[0], b[3] - b[1]
    pad_x, pad_y = 7, 4
    draw.rounded_rectangle(
        (x, y, x + w + pad_x * 2, y + h + pad_y * 2),
        radius=8,
        fill=BG,
    )
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=fill)


def draw():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    name_f = load_font(22, True)
    role_f = load_font(16)
    tag_f = load_font(16, True)
    small_f = load_font(18)

    d.text((48, 32), "Наблюдаемый процесс заявок на закупку", font=load_font(34, True), fill=INK)
    d.text(
        (48, 82),
        "1000 завершённых экземпляров. Число на стрелке показывает, сколько раз такой переход есть в журнале.",
        font=load_font(18),
        fill=MUTED,
    )

    reg = (40, 430, 300, 550)
    chk = (390, 430, 680, 550)
    mgr = (790, 430, 1160, 550)
    bud = (1260, 430, 1560, 550)
    exe = (1860, 470, 2160, 590)
    done = (2220, 470, 2440, 590)
    rework = (520, 150, 860, 270)
    extra = (1760, 150, 2160, 270)
    rejected = (390, 820, 720, 940)
    cancelled = (860, 820, 1160, 940)

    specs = [
        (reg, ["Регистрация", "заявки", "system"], SYS, LINE, INK),
        (chk, ["Первичная", "проверка", "specialist"], WHITE, LINE, INK),
        (mgr, ["Согласование", "руководителем", "manager"], WHITE, LINE, INK),
        (bud, ["Проверка", "бюджета", "finance"], WHITE, LINE, INK),
        (exe, ["Исполнение", "закупки", "procurement"], WHITE, LINE, INK),
        (done, ["Заявка", "выполнена", "911"], OK, OK_LINE, OK_LINE),
        (rework, ["Доработка", "заявки", "requester"], LOOP, CAN_LINE, INK),
        (extra, ["Дополнительное", "согласование", "director"], EXTRA, EXTRA_LINE, EXTRA_LINE),
        (rejected, ["Заявка", "отклонена", "63"], BAD, BAD_LINE, BAD_LINE),
        (cancelled, ["Заявка", "отменена", "26"], CAN, CAN_LINE, CAN_LINE),
    ]
    for box, lines, fill, outline, color in specs:
        rrect(d, box, fill, outline)
        center_text(d, box, lines, [name_f, name_f, role_f], [color, color, MUTED])

    # Прямой ряд. Стрелка останавливается до рамки.
    arrow(d, [(300, 490), (390, 490)])
    tag(d, (312, 452), "1000", tag_f)
    arrow(d, [(680, 490), (790, 490)])
    tag(d, (692, 452), "accept  1129", tag_f)
    arrow(d, [(1160, 490), (1260, 490)])
    tag(d, (1172, 452), "accept  911", tag_f)
    arrow(d, [(1560, 530), (1860, 530)])
    tag(d, (1628, 548), "до 150 тыс.   702", tag_f)
    arrow(d, [(2160, 530), (2220, 530)])
    tag(d, (2164, 492), "911", tag_f)

    # Выше порога: вверх от бюджета, влево в доп. согласование, вниз в исполнение.
    arrow(d, [(1410, 430), (1410, 210), (1760, 210)])
    tag(d, (1460, 164), "выше 150 тыс.   209", tag_f)
    arrow(d, [(1960, 270), (1960, 470)])

    # Возврат: от руководителя вверх и в доработку, из доработки вниз в проверку.
    arrow(d, [(900, 430), (900, 210), (860, 210)])
    tag(d, (908, 300), "return  174", tag_f)
    arrow(d, [(560, 270), (560, 430)])

    # Отказ на проверке, в левую часть блока.
    arrow(d, [(470, 550), (470, 820)])
    tag(d, (482, 660), "reject  45", tag_f, BAD_LINE)

    # Отказ руководителя обходит отмену слева.
    arrow(d, [(860, 550), (860, 700), (620, 700), (620, 820)])
    tag(d, (668, 662), "reject  18", tag_f, BAD_LINE)

    arrow(d, [(1010, 550), (1010, 820)])
    tag(d, (1022, 660), "cancel  26", tag_f, CAN_LINE)

    d.line([(48, 1000), (2432, 1000)], fill=(220, 214, 204), width=2)
    d.text((48, 1018), "Легенда", font=load_font(20, True), fill=INK)
    items = [
        (48, 1064, SYS, LINE, "Автоматическое действие"),
        (470, 1064, WHITE, LINE, "Человеческое задание"),
        (900, 1064, LOOP, CAN_LINE, "Возврат заявителю"),
        (1320, 1064, EXTRA, EXTRA_LINE, "Только при сумме выше 150 тысяч"),
        (48, 1148, OK, OK_LINE, "Конец: выполнена"),
        (470, 1148, BAD, BAD_LINE, "Конец: отклонена"),
        (900, 1148, CAN, CAN_LINE, "Конец: отменена"),
    ]
    legend_f = load_font(18)
    for x, y, fill, outline, text in items:
        rrect(d, (x, y, x + 28, y + 28), fill, outline, width=2, radius=6)
        d.text((x + 40, y + 2), text, font=legend_f, fill=INK)

    d.text(
        (48, 1228),
        "Петля доработки наблюдалась один раз у 138 заявок и два раза у 18. Третьего повтора в журнале нет. Бюджет, доп. согласование и исполнение всегда закрыты с accept.",
        font=small_f,
        fill=MUTED,
    )
    img.save(OUT, "PNG")
    print(OUT)


if __name__ == "__main__":
    draw()
