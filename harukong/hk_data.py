# -*- coding: utf-8 -*-
# 하루콩 - 데이터 (DB, 일과 파일, 백업, 공휴일)
from __future__ import unicode_literals
import os, io, re, sys, shutil, sqlite3, datetime

BASE = os.path.dirname(os.path.abspath(__file__)).decode(sys.getfilesystemencoding())
DATA = os.path.join(BASE, 'data')
BACKUP = os.path.join(BASE, 'backup')
DB = os.path.join(DATA, 'harukong.db')
ILGWA = os.path.join(DATA, 'ilgwa.txt')
LOG = os.path.join(DATA, 'error.log')

BLACK, RED, BLUE = '#333333', '#E53935', '#1E88E5'
COLORS = [('검정', BLACK), ('빨강', RED), ('파랑', BLUE), ('초록', '#43A047'),
          ('주황', '#FB8C00'), ('분홍', '#EC407A'), ('보라', '#8E44AD'),
          ('민트', '#00A991'), ('코랄', '#FF6F61'), ('갈색', '#8D6E63')]
THEMES = [('라벤더', '#F1EEFC', '#7058E0'), ('크림', '#FBF5E9', '#E0883A'),
          ('민트', '#EAF6F1', '#2E9E7E'), ('벚꽃', '#FCEFF3', '#D9648A'),
          ('하늘', '#EAF2FC', '#3D7FD9'), ('레몬', '#FBF8E3', '#C79A12')]
FONTS = ['양재튼튼체B', 'HY엽서M', 'HYPost-Medium', '휴먼둥근헤드라인',
         'HY견고딕', 'HYGothic-Extra', 'Malgun Gothic', '맑은 고딕']
MEMO_FONTS = ['DotumChe', '돋움체', 'GulimChe', '굴림체']
HOLIDAYS = {'01-01': '신정', '03-01': '삼일절', '05-05': '어린이날',
            '06-06': '현충일', '08-15': '광복절', '10-03': '개천절',
            '10-09': '한글날', '12-25': '성탄절'}
DATE_RE = re.compile(r'^(\d\d)\.(\d\d)\.(\d\d)\.(\(.\))?')  # 일과 날짜 줄
_con = None


def dkey(d):
    return '%04d-%02d-%02d' % (d.year, d.month, d.day)


def yoil(d):
    return '월화수목금토일'[d.weekday()]


def holiday_name(d):
    return HOLIDAYS.get('%02d-%02d' % (d.month, d.day), '')


def bg_of(accent):
    for name, bg, a in THEMES:
        if a.lower() == accent.lower():
            return bg
    return THEMES[0][1]


def ilgwa_head(d):
    return '%02d.%02d.%02d.(%s) ' % (d.year % 100, d.month, d.day, yoil(d))


def init():
    global _con
    for p in (DATA, BACKUP):
        if not os.path.isdir(p):
            os.makedirs(p)
    if not os.path.exists(ILGWA):
        write_ilgwa('')
    backup()
    _con = sqlite3.connect(DB)
    q('CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, '
      'day TEXT, time TEXT, content TEXT, color TEXT, ord INTEGER)')
    q('CREATE TABLE IF NOT EXISTS daystate (day TEXT PRIMARY KEY, '
      'text TEXT, color TEXT, holiday INTEGER)')
    q('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
    q('CREATE TABLE IF NOT EXISTS tags (text TEXT PRIMARY KEY, color TEXT)')
    q('CREATE INDEX IF NOT EXISTS ix_day ON schedule (day)')


def q(sql, args=()):
    rows = _con.execute(sql, args).fetchall()
    _con.commit()
    return rows


# ---------- 일정 ----------
def get_sched(day):
    return q('SELECT id, time, content, color FROM schedule '
             'WHERE day=? ORDER BY ord', (day,))


def month_sched(k1, k2):
    result = {}
    for r in q('SELECT day, time, content, color FROM schedule '
               'WHERE day BETWEEN ? AND ? ORDER BY day, ord', (k1, k2)):
        result.setdefault(r[0], []).append(r[1:])
    return result


def add_sched(day, time, content, color):
    rows = get_sched(day)
    pos = len(rows)
    for i, r in enumerate(rows):
        if r[1] > time:
            pos = i
            break
    cur = _con.execute('INSERT INTO schedule (day, time, content, color, ord) '
                       'VALUES (?, ?, ?, ?, 0)', (day, time, content, color))
    ids = [r[0] for r in rows]
    ids.insert(pos, cur.lastrowid)
    set_order(ids)


def update_sched(sid, time, content, color):
    q('UPDATE schedule SET time=?, content=?, color=? WHERE id=?',
      (time, content, color, sid))


def del_sched(sid):
    q('DELETE FROM schedule WHERE id=?', (sid,))


def set_order(ids):
    _con.executemany('UPDATE schedule SET ord=? WHERE id=?', [(i, sid) for i, sid in enumerate(ids)])
    _con.commit()


def copy_sched(ids, day, move):
    for sid in ids:
        t, c, col = q('SELECT time, content, color FROM schedule WHERE id=?', (sid,))[0]
        add_sched(day, t, c, col)
        if move:
            del_sched(sid)


# ---------- 날짜 상태 ----------
def get_state(day):
    return month_states(day, day).get(day, ('', RED, 0))


def set_state(day, text, color, holiday):
    if not text and holiday == 0:
        q('DELETE FROM daystate WHERE day=?', (day,))
    else:
        q('INSERT OR REPLACE INTO daystate VALUES (?, ?, ?, ?)',
          (day, text, color, holiday))


def month_states(k1, k2):
    rows = q('SELECT day, text, color, holiday FROM daystate '
             'WHERE day BETWEEN ? AND ?', (k1, k2))
    return dict((r[0], r[1:]) for r in rows)


def next_holiday(today):
    # 오늘부터 1년 안의 가장 가까운 빨간 날 → (이름, 남은 날수), 일요일은 제외
    states = month_states(dkey(today), dkey(today + datetime.timedelta(366)))
    for i in range(367):
        d = today + datetime.timedelta(i)
        text, color, holiday = states.get(dkey(d), ('', '', 0))
        name = holiday_name(d)
        if holiday == 1:
            return text or name or '빨간 날', i
        if holiday == 0 and name:
            return name, i
    return '', 0


# 하루 표시 목록 (드롭다운에 나오는 단어)
def get_tags():
    return q('SELECT text, color FROM tags ORDER BY text')


def add_tag(text, color):
    q('INSERT OR REPLACE INTO tags VALUES (?, ?)', (text, color))


def del_tag(text):
    q('DELETE FROM tags WHERE text=?', (text,))


# ---------- 설정 ----------
def get_conf(key, default):
    rows = q('SELECT value FROM config WHERE key=?', (key,))
    return rows[0][0] if rows else default


def set_conf(key, value):
    q('INSERT OR REPLACE INTO config VALUES (?, ?)', (key, value))


# ---------- 일과 파일 (메모장에서 안 깨지게 UTF-8 BOM) ----------
def read_ilgwa():
    with io.open(ILGWA, 'r', encoding='utf-8-sig') as f:
        return f.read()


def write_text(path, text):
    with io.open(path, 'w', encoding='utf-8-sig') as f:
        f.write(text)


def write_ilgwa(text):
    write_text(ILGWA, text)


# ---------- 출력 ----------
def extract_ilgwa(d1, d2):
    out = []
    keep = False
    for line in read_ilgwa().split('\n'):
        m = DATE_RE.match(line)
        if m:
            try:
                d = datetime.date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
                keep = d1 <= d <= d2
            except ValueError:
                pass
        if keep:
            out.append(line)
    return '\n'.join(out)


def extract_sched(d1, d2):
    k1, k2 = dkey(d1), dkey(d2)
    sched, states = month_sched(k1, k2), month_states(k1, k2)
    out = ['=== %s ~ %s 일정 ===' % (k1.replace('-', '.'), k2.replace('-', '.')), '']
    d = d1
    while d <= d2:
        k = dkey(d)
        text = states.get(k, ('',))[0]
        if k in sched or text:
            line = ilgwa_head(d).strip()
            if text:
                line += ' [%s]' % text
            out.append(line)
            for t, c, col in sched.get(k, []):
                out.append('    ' + (t + ' ' if t else '') + c)
        d += datetime.timedelta(1)
    return '\n'.join(out)


def save_print(name, text):
    path = os.path.join(DATA, name)
    write_text(path, text)
    os.startfile(path)


# ---------- 백업 / 오류 ----------
def backup():
    dst = os.path.join(BACKUP, dkey(datetime.date.today()))
    if not os.path.isdir(dst):
        os.makedirs(dst)
    for p in (DB, ILGWA):
        if os.path.exists(p):
            shutil.copy2(p, dst)
    for old in sorted(os.listdir(BACKUP))[:-30]:
        shutil.rmtree(os.path.join(BACKUP, old), True)


def log_error(lines):
    msg = ''.join(l if isinstance(l, unicode) else l.decode('utf-8', 'replace')
                  for l in lines)
    try:
        with io.open(LOG, 'a', encoding='utf-8') as f:
            f.write('[%s]\n%s\n' % (datetime.datetime.now(), msg))
    except Exception:
        pass
    return msg
