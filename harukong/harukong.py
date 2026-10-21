# -*- coding: utf-8 -*-
# 하루콩 - 메인 (달력 화면)
from __future__ import unicode_literals
import sip
sip.setapi('QString', 2)
sip.setapi('QVariant', 2)
import os, sys, cgi, datetime, calendar, traceback
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import hk_data as db
import hk_dialogs as dlg

HEAD, PAD = 50, 12
INK, GRAY = '#3A3550', '#9A94B0'
STYLE = '''
QWidget { background: %(bg)s; color: %(ink)s; font-family: "%(font)s"; font-size: %(size)dpt; }
QPushButton { background: white; border: 1px solid %(line)s; border-radius: 12px;
              padding: 7px 16px; font-weight: bold; }
QPushButton:hover { border-color: %(accent)s; }
QPushButton#primary { background: %(accent)s; border-color: %(accent)s; color: white; }
QPushButton#small { padding: 4px 10px; }
QPushButton#danger { padding: 4px 10px; color: #E53935; }
QWidget#topbar QPushButton { min-height: 30px; padding: 4px 18px; }
QWidget#topbar QPushButton#nav { min-width: 22px; padding: 4px 10px; font-size: %(mid)dpt; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit, QDateEdit, QSpinBox
    { background: white; border: 1px solid %(line)s; border-radius: 10px; padding: 5px;
      selection-background-color: %(accent)s; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: %(accent)s; }
QListWidget::item { padding: 5px; }
QListWidget::item:selected { background: %(soft)s; color: %(ink)s; }
QLabel#maintitle { font-size: %(huge)dpt; font-weight: bold; }
QLabel#title { font-size: %(big)dpt; font-weight: bold; }
QLabel#section { font-weight: bold; color: %(accent)s; margin-top: 6px; }
QLabel#hint { color: %(gray)s; }
QLabel#summary { color: #5A5470; font-weight: bold; }
QLabel#dday { background: %(soft)s; color: %(accent)s; font-weight: bold;
              border-radius: 12px; padding: 6px 14px; }
QToolTip { background: white; color: %(ink)s; border: 1px solid %(line)s; padding: 6px;
           font-family: "%(font)s"; }
QCalendarWidget QAbstractItemView { selection-background-color: %(accent)s; selection-color: white; }
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 24px; }
QComboBox::down-arrow, QDateEdit::down-arrow { image: url(%(arrow)s); }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: %(line)s; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
'''


def soft(color, alpha):
    c = QColor(color)
    c.setAlpha(alpha)
    return c


def rgba(color, alpha):
    c = QColor(color)
    return 'rgba(%d, %d, %d, %d)' % (c.red(), c.green(), c.blue(), alpha)


def make_icon(color):
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(4, 10, 56, 46))
    p.setBrush(QColor('white'))
    p.drawEllipse(QRectF(20, 26, 7, 9))
    p.drawEllipse(QRectF(37, 26, 7, 9))
    p.end()
    return QIcon(pix)


def make_arrow(color):
    pix = QPixmap(12, 8)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 2))
    p.drawPolyline(QPolygonF([QPointF(1, 1), QPointF(6, 6), QPointF(11, 1)]))
    p.end()
    path = os.path.join(db.DATA, 'arrow.png')
    pix.save(path)
    return path.replace('\\', '/')


def pick_font(cands):
    fams = QFontDatabase().families()
    for f in cands:
        if f in fams:
            return f
    return cands[-1]


class CalendarView(QWidget):
    def __init__(self, main):
        QWidget.__init__(self)
        self.main = main
        self.hover = -1
        self.fonts = {}
        self.setMouseTracking(True)

    def set_month(self, year, month):
        first = datetime.date(year, month, 1)
        skip = (first.weekday() + 1) % 7
        self.nrows = (skip + calendar.monthrange(year, month)[1] + 6) // 7
        start = first - datetime.timedelta(skip)
        self.days = [start + datetime.timedelta(i) for i in range(self.nrows * 7)]
        self.keys = [db.dkey(d) for d in self.days]
        self.month = month
        self.sched = db.month_sched(self.keys[0], self.keys[-1])
        self.states = db.month_states(self.keys[0], self.keys[-1])
        self.update()

    def font(self, size, bold=False):
        # 글꼴은 한 번 만들어서 재사용 (속도)
        if (size, bold) not in self.fonts:
            f = QFont(self.main.font_name, size, QFont.Bold if bold else QFont.Normal)
            self.fonts[size, bold] = (f, QFontMetrics(f))
        return self.fonts[size, bold]

    def cell_size(self):
        return (self.width() - PAD * 2) / 7.0, (self.height() - HEAD - PAD) / float(self.nrows)

    def cell_rect(self, i):
        w, h = self.cell_size()
        return QRectF(PAD + (i % 7) * w, HEAD + (i // 7) * h, w, h)

    def index_at(self, pos):
        w, h = self.cell_size()
        c, r = int((pos.x() - PAD) / w), int((pos.y() - HEAD) / h)
        if pos.x() < PAD or pos.y() < HEAD or c > 6 or r >= self.nrows:
            return -1
        return r * 7 + c

    def day_info(self, i):
        # (날짜, 하루 표시, 색, 공휴일명, 날짜숫자 색)
        d = self.days[i]
        text, color, holiday = self.states.get(self.keys[i], ('', db.RED, 0))
        hname = db.holiday_name(d) if holiday == 0 else ''
        if holiday == 1 or (holiday == 0 and (hname or d.weekday() == 6)):
            num = db.RED
        else:
            num = db.BLUE if d.weekday() == 5 else INK
        return d, text, color, hname, num

    def set_hover(self, i):
        # 바뀐 두 칸만 다시 그림 (속도)
        if i != self.hover:
            for j in (self.hover, i):
                if j >= 0:
                    self.update(self.cell_rect(j).toAlignedRect())
            self.hover = i

    def mouseMoveEvent(self, e):
        self.set_hover(self.index_at(e.pos()))

    def leaveEvent(self, e):
        self.set_hover(-1)

    def mouseDoubleClickEvent(self, e):
        i = self.index_at(e.pos())
        if i >= 0 and e.button() == Qt.LeftButton:
            self.main.open_sched(self.days[i])

    def contextMenuEvent(self, e):
        i = self.index_at(e.pos())
        if i >= 0:
            self.main.open_ilgwa(self.days[i])

    def event(self, e):
        # 마우스를 올리고 잠시 있으면 그날 일정 전체를 말풍선으로
        if e.type() == QEvent.ToolTip:
            i = self.index_at(e.pos())
            if i >= 0:
                QToolTip.showText(e.globalPos(), self.tip(i), self,
                                  self.cell_rect(i).toAlignedRect())
            return True
        return QWidget.event(self, e)

    def tip(self, i):
        d, text, color, hname, num = self.day_info(i)
        html = '<b style="color:%s">%d월 %d일 (%s)</b>' % (num, d.month, d.day, db.yoil(d))
        for s, col in ((hname, db.RED), (text, color)):
            if s:
                html += ' &nbsp;<b style="color:%s">%s</b>' % (col, cgi.escape(s))
        for t, c, col in self.sched.get(self.keys[i], []):
            html += '<br><b style="color:%s">%s</b> <span style="color:%s">%s</span>' % (
                self.main.accent, t, col, cgi.escape(c))
        return html + '<br><span style="color:%s">더블클릭: 일정 · 우클릭: 하루 일과</span>' % GRAY

    def paintEvent(self, e):
        m = self.main
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(m.bg))
        p.setPen(QPen(soft(m.accent, 40), 1))
        p.setBrush(QColor('white'))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 18, 18)
        p.setFont(self.font(m.font_size + 2, True)[0])
        for c in range(7):
            r = self.cell_rect(c)
            p.setPen(QColor(db.RED if c == 0 else db.BLUE if c == 6 else '#5A5470'))
            p.drawText(QRectF(r.x(), 4, r.width(), HEAD - 4), Qt.AlignCenter, '일월화수목금토'[c])
        area = QRectF(e.rect())
        for i in range(len(self.days)):
            r = self.cell_rect(i)
            if r.intersects(area):
                self.draw_cell(p, r.adjusted(3, 3, -3, -3), i)

    def draw_cell(self, p, r, i):
        m = self.main
        d, text, color, hname, num = self.day_info(i)
        other = d.month != self.month
        fill = QColor('#F5F9FF' if d.weekday() == 5 else '#FFF6F8' if d.weekday() == 6 else 'white')
        pen = QPen(soft(m.accent, 55), 1)
        if other:
            fill = soft(m.accent, 15)
        if i == self.hover:
            pen = QPen(soft(m.accent, 150), 1.5)
        if d == m.today:
            fill = soft(m.accent, 22)
            pen = QPen(QColor(m.accent), 2)
        p.setPen(pen)
        p.setBrush(fill)
        p.drawRoundedRect(r, 10, 10)
        p.setOpacity(0.4 if other else 1)

        # 1줄: 날짜숫자 + 공휴일명 + 하루 표시(알약 모양)
        x, y, right = r.x() + 8, r.y() + 5, r.right() - 6
        f, fm = self.font(m.font_size + 2, True)
        line_h = fm.height()
        p.setFont(f)
        p.setPen(QColor(num))
        p.drawText(QPointF(x, y + fm.ascent()), '%d' % d.day)
        x += fm.width('%d' % d.day) + 6
        f, fm = self.font(m.font_size - 1, True)
        p.setFont(f)
        if hname:
            p.setPen(QColor(db.RED))
            p.drawText(QRectF(x, y, right - x, line_h), Qt.AlignVCenter, hname)
            x += fm.width(hname) + 6
        s = fm.elidedText(text, Qt.ElideRight, int(right - x - 12))
        if s:
            pill = QRectF(x, y + 2, fm.width(s) + 12, line_h - 4)
            p.setPen(Qt.NoPen)
            p.setBrush(soft(color, 40))
            p.drawRoundedRect(pill, 8, 8)
            p.setPen(QColor(color))
            p.drawText(pill, Qt.AlignCenter, s)

        # 2줄~: 일정 (넘치면 글자 축소, 그래도 넘치면 +N개)
        items = self.sched.get(self.keys[i], [])
        x, top = r.x() + 8, y + line_h + 4
        avail = r.bottom() - top - 4
        size = m.font_size - 1
        while size > 7 and self.font(size)[1].lineSpacing() * len(items) > avail:
            size -= 1
        f, fm = self.font(size)
        fb, fmb = self.font(size, True)
        lh = fm.lineSpacing()
        maxn = max(int(avail / lh), 1)
        if len(items) > maxn:
            items, more = items[:maxn - 1], len(items) - maxn + 1
        else:
            more = 0
        for t, c, col in items:
            xx, base = x, top + fm.ascent()
            if t:
                p.setFont(fb)
                p.setPen(QColor(m.accent))
                p.drawText(QPointF(xx, base), t)
                xx += fmb.width(t) + 5
            p.setFont(f)
            p.setPen(QColor(col))
            p.drawText(QPointF(xx, base), fm.elidedText(c, Qt.ElideRight, int(right - xx)))
            top += lh
        if more:
            p.setPen(QColor(GRAY))
            p.drawText(QPointF(x, top + fm.ascent()), '+%d개 더' % more)
        p.setOpacity(1)


class Main(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setWindowTitle('하루콩')
        self.today = datetime.date.today()
        self.year, self.month = self.today.year, self.today.month
        self.ilgwa = None
        self.load_conf()
        self.cal = CalendarView(self)
        self.title = dlg.label('', 'maintitle')
        self.title.setMinimumWidth(190)
        self.title.setAlignment(Qt.AlignCenter)
        self.dday = dlg.label('', 'dday')
        self.summary = dlg.label('', 'summary')
        bar = QWidget()
        bar.setObjectName('topbar')
        top = QHBoxLayout(bar)
        top.setContentsMargins(0, 0, 0, 0)
        dlg.buttons([('<', lambda: self.move_month(-1), 'nav')], top)
        top.addSpacing(36)
        top.addWidget(self.title)
        top.addSpacing(36)
        dlg.buttons([('>', lambda: self.move_month(1), 'nav')], top)
        top.addSpacing(6)
        dlg.buttons([('오늘', self.go_today, 'primary')], top)
        top.addSpacing(12)
        top.addWidget(self.dday)
        top.addStretch()
        dlg.buttons([('하루 일과', lambda: self.open_ilgwa(None)),
                     ('출력', self.open_print), ('설정', self.open_conf)], top)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 16)
        lay.setSpacing(12)
        lay.addWidget(bar)
        lay.addWidget(self.cal, 1)
        lay.addWidget(self.summary)
        timer = QTimer(self)
        timer.timeout.connect(self.tick)
        timer.start(60000)
        self.apply_style()
        self.refresh()

    def tick(self):
        # 1분마다: 일과가 바뀌었으면 자동 저장 (PC가 그냥 꺼져도 최대 1분만 잃음)
        if self.ilgwa and self.ilgwa.edit.document().isModified():
            self.ilgwa.save()
        # 켜둔 채 날짜가 바뀌면: 백업 + 오늘 표시, D-day 갱신
        if datetime.date.today() != self.today:
            self.today = datetime.date.today()
            db.backup()
            self.refresh()

    def load_conf(self):
        self.accent = db.get_conf('accent', db.THEMES[0][2])
        self.bg = db.bg_of(self.accent)
        self.font_name = db.get_conf('font', '') or pick_font(db.FONTS)
        self.font_size = int(db.get_conf('size', '11'))
        self.memo_font = db.get_conf('memo_font', '') or pick_font(db.MEMO_FONTS)

    def apply_style(self):
        # 프로그램 전체(모든 창, 말풍선, 메시지창)에 한 번에 적용
        qApp.setStyleSheet(STYLE % {
            'bg': self.bg, 'accent': self.accent, 'ink': INK, 'gray': GRAY,
            'line': rgba(self.accent, 70), 'soft': rgba(self.accent, 40),
            'font': self.font_name, 'size': self.font_size, 'mid': self.font_size + 2,
            'big': self.font_size + 7, 'huge': self.font_size + 9,
            'arrow': make_arrow(self.accent)})
        qApp.setWindowIcon(make_icon(self.accent))
        self.cal.fonts = {}
        if self.ilgwa:
            self.ilgwa.apply_style()

    def refresh(self):
        self.title.setText('%d년 %d월' % (self.year, self.month))
        self.cal.set_month(self.year, self.month)
        # 이번 달 요약: 일정 개수 + 하루 표시별 횟수
        n, count = 0, {}
        for d, k in zip(self.cal.days, self.cal.keys):
            if d.month == self.month:
                n += len(self.cal.sched.get(k, []))
                text = self.cal.states.get(k, ('',))[0]
                if text:
                    count[text] = count.get(text, 0) + 1
        parts = ['일정 %d개' % n]
        parts += ['%s %d' % (t, c) for t, c in sorted(count.items(), key=lambda x: -x[1])]
        self.summary.setText('%d월        %s' % (self.month, '   ·   '.join(parts)))
        # 다음 빨간 날까지 D-day
        name, days = db.next_holiday(self.today)
        self.dday.setText('오늘은 %s' % name if days == 0 else '%s까지 D-%d' % (name, days))
        self.dday.setVisible(bool(name))

    def move_month(self, step):
        m = self.year * 12 + self.month - 1 + step
        self.year, self.month = m // 12, m % 12 + 1
        self.refresh()

    def go_today(self):
        self.year, self.month = self.today.year, self.today.month
        self.refresh()

    def open_sched(self, d):
        dlg.SchedDialog(self, d).exec_()
        self.refresh()

    def open_ilgwa(self, d):
        if self.ilgwa is None:
            self.ilgwa = dlg.IlgwaWindow(self)
        self.ilgwa.show()
        self.ilgwa.raise_()
        self.ilgwa.activateWindow()
        self.ilgwa.goto(d)

    def open_print(self):
        dlg.PrintDialog(self, self.year, self.month).exec_()

    def open_conf(self):
        if dlg.ConfDialog(self).exec_():
            self.load_conf()
            self.apply_style()
            self.refresh()

    def closeEvent(self, e):
        if self.ilgwa:
            self.ilgwa.close()
        e.accept()


def on_error(t, v, tb):
    msg = db.log_error(traceback.format_exception(t, v, tb))
    QMessageBox.critical(None, '하루콩 오류', msg[-1500:])


def main():
    app = QApplication(sys.argv)
    sys.excepthook = on_error
    db.init()
    w = Main()
    w.showMaximized()
    app.exec_()


if __name__ == '__main__':
    main()
