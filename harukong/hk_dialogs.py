# -*- coding: utf-8 -*-
# 하루콩 - 창 모음 (일정창, 일과창, 출력창, 설정창)
from __future__ import unicode_literals
import datetime
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import hk_data as db


class Button(QPushButton):
    # 버튼에 커서가 있을 때 Enter(키패드 Enter 포함)로도 누르기
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            QPushButton.keyPressEvent(self, e)


def buttons(items, lay=None):
    # items: (글자, 함수) 또는 (글자, 함수, 'primary'/'small')
    if lay is None:
        lay = QHBoxLayout()
    for item in items:
        b = Button(item[0])
        b.setAutoDefault(False)
        b.clicked.connect(item[1])
        if len(item) > 2:
            b.setObjectName(item[2])
        lay.addWidget(b)
    return lay


def label(text, name):
    w = QLabel(text)
    w.setObjectName(name)
    return w


def warn(parent, msg):
    QMessageBox.warning(parent, '하루콩', msg)


def setup_calendar(cal):
    # 작은 달력: 일요일 시작, 주차 번호 없음, 토요일 파랑
    cal.setFirstDayOfWeek(Qt.Sunday)
    cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
    cal.setMinimumSize(380, 280)
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(db.BLUE))
    cal.setWeekdayTextFormat(Qt.Saturday, fmt)


def pick_date(parent, title):
    d = QDialog(parent)
    d.setWindowTitle(title)
    cal = QCalendarWidget()
    setup_calendar(cal)
    cal.activated.connect(lambda qd: d.accept())
    lay = QVBoxLayout(d)
    lay.addWidget(cal)
    lay.addLayout(buttons([('취소', d.reject), ('확인', d.accept, 'primary')]))
    if d.exec_():
        return cal.selectedDate().toPyDate()
    return None


class NumSpin(QSpinBox):
    # 7 → 07 처럼 두 자리로 표시, 두 자리를 치면 다음 칸으로
    def __init__(self):
        QSpinBox.__init__(self)
        self.next = None
        self.lineEdit().textEdited.connect(self.typed)

    def typed(self, t):
        if len(t) >= 2 and self.next:
            QTimer.singleShot(0, self.next.setFocus)

    def focusInEvent(self, e):
        # 칸에 들어오면 전체 선택 → '--' 에서도 바로 숫자 입력
        QSpinBox.focusInEvent(self, e)
        QTimer.singleShot(0, self.selectAll)

    def textFromValue(self, v):
        return '%02d' % v

    def stepBy(self, n):
        # 휠을 돌리면 끝에서 처음으로 돌아감 (55분 → 00분, 23시 → --)
        lo = self.minimum()
        self.setValue(lo + (self.value() - lo + n * self.singleStep()) % (self.maximum() - lo + 1))


class TimeBox(QWidget):
    # 알람처럼 시, 분을 마우스 휠로 선택 (시가 -- 이면 시간 없음)
    def __init__(self, t=''):
        QWidget.__init__(self)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.h, self.m = NumSpin(), NumSpin()
        for w, lo, hi, step in ((self.h, -1, 23, 1), (self.m, 0, 59, 5)):
            w.setRange(lo, hi)
            w.setSingleStep(step)
            w.setWrapping(True)
            w.setAlignment(Qt.AlignCenter)
            w.setButtonSymbols(QAbstractSpinBox.NoButtons)
            w.setFixedWidth(52)
        self.h.setSpecialValueText('--')
        lay.addWidget(self.h)
        lay.addWidget(QLabel(':'))
        lay.addWidget(self.m)
        self.set_text(t)

    def text(self):
        if self.h.value() < 0:
            return ''
        return '%02d:%02d' % (self.h.value(), self.m.value())

    def set_text(self, t):
        self.h.setValue(int(t[:2]) if t else -1)
        self.m.setValue(int(t[3:]) if t else 0)

    def link(self, after):
        # 시 → 분 → 할 일 순서로 이동 (두 자리 입력, Tab 모두)
        self.h.next, self.m.next = self.m, after
        QWidget.setTabOrder(self.h, self.m)
        QWidget.setTabOrder(self.m, after)


def read_input(parent, time, content, color):
    c = content.text().strip()
    if not c:
        return warn(parent, '할 일을 입력해 주세요')
    return time.text(), c, color.color


class ColorBar(QWidget):
    def __init__(self, color, colors=db.COLORS):
        QWidget.__init__(self)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.btns = []
        for name, c in colors:
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setToolTip(name)
            b.clicked.connect(lambda checked=False, c=c: self.set_color(c))
            lay.addWidget(b)
            self.btns.append((b, c))
        self.custom_btn = QPushButton('직접')
        self.custom_btn.setObjectName('small')
        self.custom_btn.clicked.connect(self.custom)
        lay.addWidget(self.custom_btn)
        lay.addStretch()
        self.set_color(color)

    def set_color(self, color):
        self.color = color
        for b, c in self.btns:
            on = c.lower() == color.lower()
            check = '#333333' if QColor(c).lightness() > 170 else 'white'
            line = '2px solid #3A3550' if on else '1px solid rgba(0, 0, 0, 25)'
            b.setText('✓' if on else '')
            b.setStyleSheet('background: %s; color: %s; border: %s; border-radius: 13px; '
                            'padding: 0; font-weight: bold;' % (c, check, line))
        self.custom_btn.setStyleSheet('border: 2px solid %s;' % color)

    def custom(self):
        c = QColorDialog.getColor(QColor(self.color), self)
        if c.isValid():
            self.set_color(c.name())


class ItemDialog(QDialog):
    # 일정 하나 수정하는 작은 창
    def __init__(self, parent, t, c, col):
        QDialog.__init__(self, parent)
        self.setWindowTitle('하루콩 - 일정 수정')
        self.resize(480, 10)
        self.time = TimeBox(t)
        self.content = QLineEdit(c)
        self.content.returnPressed.connect(self.accept)
        self.color = ColorBar(col)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(label('일정 수정', 'title'))
        row = QHBoxLayout()
        row.addWidget(self.time)
        row.addWidget(self.content, 1)
        lay.addLayout(row)
        lay.addWidget(self.color)
        row = QHBoxLayout()
        row.addStretch()
        buttons([('취소', self.reject), ('저장', self.accept, 'primary')], row)
        lay.addLayout(row)
        self.time.link(self.content)
        self.content.setFocus()

    def accept(self):
        self.value = read_input(self, self.time, self.content, self.color)
        if self.value:
            QDialog.accept(self)


class SchedDialog(QDialog):
    def __init__(self, main, d):
        QDialog.__init__(self, main)
        self.day = db.dkey(d)
        self.setWindowTitle('하루콩 - %d.%02d.%02d.' % (d.year, d.month, d.day))
        self.resize(520, 640)
        text, color, holiday = db.get_state(self.day)
        self.orig = text

        self.tag = QComboBox()
        self.tag.setEditable(True)
        self.tag.setInsertPolicy(QComboBox.NoInsert)
        self.tag.lineEdit().setPlaceholderText('예: 당직, 비번, 휴가, 체육대회')
        self.tag.activated.connect(self.tag_chosen)
        self.tag_color = ColorBar(color)
        self.load_tags()
        self.tag.setEditText(text)
        self.holiday = QComboBox()
        self.holiday.addItems(['자동', '빨간 날', '평일'])
        self.holiday.setCurrentIndex(holiday)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self.edit)
        self.time = TimeBox()
        self.content = QLineEdit()
        self.content.setPlaceholderText('할 일 (Enter로 추가)')
        self.content.returnPressed.connect(self.add)
        self.color = ColorBar(db.BLACK)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)
        row = QHBoxLayout()
        row.addWidget(label('%d월 %d일 %s요일' % (d.month, d.day, db.yoil(d)), 'title'))
        row.addWidget(label('%d년' % d.year, 'hint'))
        row.addStretch()
        lay.addLayout(row)

        lay.addWidget(label('하루 표시', 'section'))
        row = QHBoxLayout()
        row.addWidget(self.tag, 1)
        buttons([('제거', self.remove_tag, 'small')], row)
        row.addSpacing(8)
        row.addWidget(QLabel('휴일'))
        row.addWidget(self.holiday)
        lay.addLayout(row)
        lay.addWidget(self.tag_color)

        row = QHBoxLayout()
        row.addWidget(label('일정', 'section'))
        row.addWidget(label('더블클릭하면 수정', 'hint'))
        row.addStretch()
        lay.addLayout(row)
        mid = QHBoxLayout()
        mid.addWidget(self.list, 1)
        side = buttons([('▲', lambda: self.shift(-1), 'small'),
                        ('▼', lambda: self.shift(1), 'small')], QVBoxLayout())
        side.addSpacing(14)
        buttons([('수정', self.edit, 'small'), ('복사', lambda: self.copy(False), 'small'),
                 ('이동', lambda: self.copy(True), 'small')], side)
        side.addSpacing(14)
        buttons([('삭제', self.delete, 'danger')], side)
        side.addStretch()
        mid.addLayout(side)
        lay.addLayout(mid)
        row = QHBoxLayout()
        row.addWidget(self.time)
        row.addWidget(self.content, 1)
        buttons([('추가', self.add, 'primary')], row)
        lay.addLayout(row)
        lay.addWidget(self.color)
        row = QHBoxLayout()
        row.addStretch()
        buttons([('확인', self.ok, 'primary')], row)
        lay.addSpacing(6)
        lay.addLayout(row)
        self.load()
        self.time.link(self.content)
        self.time.h.setFocus()

    def ok(self):
        # 할 일 칸에 쓰다 만 내용이 있으면 추가하고 닫기
        if self.content.text().strip():
            self.add()
        self.accept()

    def done(self, r):
        text = self.tag.currentText().strip()
        db.set_state(self.day, text, self.tag_color.color, self.holiday.currentIndex())
        if text and (text != self.orig or text in self.tags):
            db.add_tag(text, self.tag_color.color)
        QDialog.done(self, r)

    def load_tags(self):
        text = self.tag.currentText()
        rows = db.get_tags()
        self.tags = dict(rows)
        self.tag.clear()
        self.tag.addItem('')
        for t, c in rows:
            self.tag.addItem(t)
            self.tag.setItemData(self.tag.count() - 1, QColor(c), Qt.ForegroundRole)
        self.tag.setEditText(text)

    def tag_chosen(self, i):
        t = self.tag.itemText(i)
        if t in self.tags:
            self.tag_color.set_color(self.tags[t])

    def remove_tag(self):
        t = self.tag.currentText().strip()
        if t not in self.tags:
            return warn(self, '제거할 단어를 드롭다운에서 먼저 골라 주세요')
        db.del_tag(t)
        self.load_tags()
        QMessageBox.information(self, '하루콩', "'%s'을(를) 드롭다운 목록에서 제거했어요." % t)

    def load(self):
        self.rows = db.get_sched(self.day)
        self.list.clear()
        for sid, t, c, col in self.rows:
            item = QListWidgetItem((t + '   ' if t else '') + c)
            item.setForeground(QColor(col))
            self.list.addItem(item)

    def sel(self):
        return sorted(self.list.row(item) for item in self.list.selectedItems())

    def add(self):
        v = read_input(self, self.time, self.content, self.color)
        if v:
            db.add_sched(self.day, *v)
            self.time.set_text('')
            self.content.clear()
            self.load()
            self.time.h.setFocus()

    def edit(self, *args):
        s = self.sel()
        if len(s) != 1:
            return warn(self, '수정할 일정을 하나만 선택해 주세요')
        sid, t, c, col = self.rows[s[0]]
        d = ItemDialog(self, t, c, col)
        if d.exec_():
            db.update_sched(sid, *d.value)
            self.load()
            self.list.setCurrentRow(s[0])

    def delete(self):
        s = self.sel()
        if s and QMessageBox.question(self, '하루콩', '선택한 일정을 삭제할까요?',
                                      QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            for i in s:
                db.del_sched(self.rows[i][0])
            self.load()

    def shift(self, step):
        s = self.sel()
        if len(s) != 1:
            return
        i, j = s[0], s[0] + step
        if 0 <= j < len(self.rows):
            ids = [r[0] for r in self.rows]
            ids[i], ids[j] = ids[j], ids[i]
            db.set_order(ids)
            self.load()
            self.list.setCurrentRow(j)

    def copy(self, move):
        s = self.sel()
        if not s:
            return warn(self, '일정을 먼저 선택해 주세요')
        d = pick_date(self, '이동할 날짜' if move else '복사할 날짜')
        if d:
            db.copy_sched([self.rows[i][0] for i in s], db.dkey(d), move)
            self.load()
            QMessageBox.information(self, '하루콩', '%d월 %d일로 %s했어요' % (
                d.month, d.day, '이동' if move else '복사'))


class DateHighlighter(QSyntaxHighlighter):
    # 일과창에서 '26.10.21.(수)' 부분만 색칠
    def __init__(self, doc):
        QSyntaxHighlighter.__init__(self, doc)
        self.fmt = QTextCharFormat()
        self.fmt.setFontWeight(QFont.Bold)

    def set_color(self, color):
        self.fmt.setForeground(QColor(color))
        self.rehighlight()

    def highlightBlock(self, text):
        m = db.DATE_RE.match(text)
        if m:
            self.setFormat(0, m.end(), self.fmt)


class IlgwaWindow(QWidget):
    def __init__(self, main):
        QWidget.__init__(self)
        self.main = main
        self.setAttribute(Qt.WA_StyledBackground)
        self.setWindowTitle('하루콩 - 하루 일과')
        self.resize(720, 860)
        self.edit = QPlainTextEdit()
        self.edit.setPlainText(db.read_ilgwa())
        self.hl = DateHighlighter(self.edit.document())
        self.status = label('', 'hint')
        for key, func in (('Ctrl+D', self.insert_today), ('Ctrl+S', self.save)):
            QShortcut(QKeySequence(key), self).activated.connect(func)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        top.addWidget(label('하루 일과', 'title'))
        top.addStretch()
        buttons([('저장  Ctrl+S', self.save),
                 ('오늘 날짜 넣기  Ctrl+D', self.insert_today, 'primary')], top)
        lay.addLayout(top)
        lay.addWidget(self.edit)
        lay.addWidget(self.status)
        self.apply_style()

    def apply_style(self):
        self.setStyleSheet('QPlainTextEdit { font-family: "%s"; padding: 10px; }' % self.main.memo_font)
        self.edit.ensurePolished()
        self.edit.setTabStopWidth(self.edit.fontMetrics().width(' ') * 4)
        self.hl.set_color(self.main.accent)

    def goto(self, d):
        c = QTextCursor()
        if d:
            c = self.edit.document().find(QRegExp('^' + QRegExp.escape(db.ilgwa_head(d)[:9])))
        if c.isNull():
            self.edit.moveCursor(QTextCursor.End)
        else:
            c.setPosition(c.selectionStart())
            self.edit.setTextCursor(c)
            self.edit.centerCursor()
        self.edit.setFocus()

    def insert_today(self):
        nl = '\n' if self.edit.document().lastBlock().text() else ''
        self.edit.moveCursor(QTextCursor.End)
        self.edit.insertPlainText(nl + db.ilgwa_head(datetime.date.today()))
        self.edit.setFocus()

    def save(self):
        db.write_ilgwa(self.edit.toPlainText())
        self.edit.document().setModified(False)
        self.status.setText('저장됨 %s' % datetime.datetime.now().strftime('%H:%M'))

    def closeEvent(self, e):
        self.save()
        e.accept()


class PrintDialog(QDialog):
    def __init__(self, main, year, month):
        QDialog.__init__(self, main)
        self.main = main
        self.setWindowTitle('하루콩 - 출력')
        first = QDate(year, month, 1)
        self.d1 = QDateEdit(first)
        self.d2 = QDateEdit(first.addMonths(1).addDays(-1))
        form = QFormLayout()
        for text, w in (('시작일', self.d1), ('종료일', self.d2)):
            w.setCalendarPopup(True)
            w.setDisplayFormat('yyyy.MM.dd')
            setup_calendar(w.calendarWidget())
            form.addRow(text, w)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.addWidget(label('출력', 'title'))
        lay.addWidget(label('기간을 고르고 출력할 내용을 누르세요. 메모장으로 열려요.', 'hint'))
        lay.addLayout(form)
        lay.addLayout(buttons([('하루 일과', self.out_ilgwa, 'primary'),
                               ('일정', self.out_sched, 'primary')]))

    def dates(self):
        return sorted([self.d1.date().toPyDate(), self.d2.date().toPyDate()])

    def out_ilgwa(self):
        if self.main.ilgwa:
            self.main.ilgwa.save()
        db.save_print('print_ilgwa.txt', db.extract_ilgwa(*self.dates()))

    def out_sched(self):
        db.save_print('print_ilgeong.txt', db.extract_sched(*self.dates()))


class ConfDialog(QDialog):
    def __init__(self, main):
        QDialog.__init__(self, main)
        self.setWindowTitle('하루콩 - 설정')
        self.theme = ColorBar(main.accent, [(t[0], t[2]) for t in db.THEMES])
        self.font = QFontComboBox()
        self.memo = QFontComboBox()
        for w, name in ((self.font, main.font_name), (self.memo, main.memo_font)):
            w.setWritingSystem(QFontDatabase.Korean)
            w.setCurrentFont(QFont(name))
        self.size = QSpinBox()
        self.size.setRange(8, 20)
        self.size.setValue(main.font_size)
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow('테마', self.theme)
        form.addRow('달력 글꼴', self.font)
        form.addRow('글자 크기', self.size)
        form.addRow('일과 글꼴', self.memo)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.addWidget(label('설정', 'title'))
        lay.addLayout(form)
        row = QHBoxLayout()
        row.addStretch()
        buttons([('취소', self.reject), ('저장', self.accept, 'primary')], row)
        lay.addLayout(row)

    def accept(self):
        db.set_conf('accent', self.theme.color)
        db.set_conf('font', self.font.currentFont().family())
        db.set_conf('size', '%d' % self.size.value())
        db.set_conf('memo_font', self.memo.currentFont().family())
        QDialog.accept(self)
