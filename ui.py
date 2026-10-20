"""Curses UI: podcast list -> episode list -> player screen (art card, big play
triangle, scrubber, skip controls), styled after a phone music player."""
import curses, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player as P

try:
    import pi18n
    S = pi18n.load('podcasts', None)
except Exception:
    S = None

DEFAULT_STRINGS = {
 'APP_TITLE': 'PODCASTS',
 'EMPTY': 'No podcasts yet. Drop .wav episodes in ~/podcasts/<Show Name>/ and restart.',
 'EPISODES_OF': 'Episodes',
 'CONTROLS_LIST': 'Up/Down choose | Enter open | q back',
 'CONTROLS_PLAYER': 'Space play/pause | Left/Right 10s | R restart | q back',
 'DONE': 'done',
 'RESUME': 'resume',
 'NO_AUDIO': 'Cannot play: aplay (ALSA) not found or file unreadable.',
}
if S is None:
    S = DEFAULT_STRINGS

TRIANGLE = ['   ', '  ', ' ', '', ' ', '  ', '   ']
TRIANGLE_ART = [
 '  █        ',
 '  ████     ',
 '  ███████  ',
 '  █████████',
 '  ███████  ',
 '  ████     ',
 '  █        ',
]
PAUSE_ART = [
 '  ██   ██  ',
 '  ██   ██  ',
 '  ██   ██  ',
 '  ██   ██  ',
 '  ██   ██  ',
 '  ██   ██  ',
 '  ██   ██  ',
]

def art_for(pod_dir):
    """Optional cover.txt art per podcast, else a generated card."""
    cover = os.path.join(pod_dir, 'cover.txt')
    try:
        with open(cover) as fh:
            return fh.read().rstrip('\n').split('\n')[:7]
    except OSError:
        name = os.path.basename(pod_dir).upper()
        # wrap the show name across the card's middle rows
        rows, cur = [], ''
        for wd in name.split():
            if len(cur) + len(wd) + 1 > 20:
                rows.append(cur.strip()); cur = ''
            cur += wd + ' '
        if cur.strip():
            rows.append(cur.strip())
        card = ['+' + '-' * 22 + '+']
        for i in range(5):
            w = rows[i] if i < len(rows) else ''
            card.append('|' + w[:20].center(22) + '|')
        card.append('+' + '-' * 22 + '+')
        return card

def draw_player(scr, pod, ep_path, pl, prog):
    scr.erase()
    h, w = scr.getmaxyx()
    key = P.episode_key(ep_path)
    put = lambda y, x, t, c=0: scr.addnstr(y, x, t, max(0, w - x - 1), c) if 0 <= y < h else None
    put(0, 2, S['APP_TITLE'] + '  -  ' + pod, curses.A_BOLD)
    title = os.path.splitext(os.path.basename(ep_path))[0]
    art = art_for(os.path.dirname(ep_path))
    ay = max(2, h // 2 - 9)
    ax = max(2, (w - 26) // 2)
    for i, line in enumerate(art):
        put(ay + i, ax, line, curses.A_DIM)
    put(ay + 8, ax, title.center(24)[:24], curses.A_BOLD)
    icon = PAUSE_ART if pl.playing() else TRIANGLE_ART
    iy = ay + 10
    for i, line in enumerate(icon):
        put(iy + i, max(2, (w - 12) // 2), line, curses.A_BOLD)
    pos, dur = pl.position(), pl.duration
    bar_y = iy + 8
    bar_w = min(w - 10, 50)
    filled = int(bar_w * (pos / dur)) if dur else 0
    bar = '#' * filled + '-' * (bar_w - filled)
    put(bar_y, 5, '[' + bar + ']')
    put(bar_y + 1, 5, P.fmt_time(pos) + ' / ' + (P.fmt_time(dur) if dur else '?:??'))
    state = prog.get(key, {})
    if state.get('done'):
        put(bar_y + 1, 5 + 24, S['DONE'], curses.A_DIM)
    put(h - 1, 2, S['CONTROLS_PLAYER'], curses.A_DIM)
    scr.refresh()

def run_player(scr, pod, ep_path, pl, prog):
    key = P.episode_key(ep_path)
    state = prog.get(key, {})
    start_at = state.get('pos', 0.0) if not state.get('done') else 0.0
    try:
        pl.play(ep_path, start_at)
    except FileNotFoundError:
        pl.path = None
    scr.timeout(200)
    saved_at = time.monotonic()
    while True:
        draw_player(scr, pod, ep_path, pl, prog)
        if pl.path is None:
            scr.addnstr(1, 2, S['NO_AUDIO'], 60, curses.A_BOLD)
            scr.refresh()
        if pl.finished():
            pos = pl.stop()
            prog[key] = {'pos': 0.0, 'done': True}
            P.save_progress(prog)
            pl.play(ep_path, 0.0)
            pl.pause()
        now = time.monotonic()
        if now - saved_at > 5:
            prog[key] = {'pos': pl.position(), 'done': prog.get(key, {}).get('done', False)}
            P.save_progress(prog)
            saved_at = now
        k = scr.getch()
        if k in (ord('q'), 27):
            prog[key] = {'pos': pl.position(), 'done': prog.get(key, {}).get('done', False)}
            P.save_progress(prog)
            pl.stop()
            return
        if k == ord(' '):
            pl.toggle()
        elif k == curses.KEY_LEFT:
            pl.seek(-P.SEEK_STEP)
        elif k == curses.KEY_RIGHT:
            pl.seek(P.SEEK_STEP)
        elif k in (ord('r'), ord('R')):
            pl.seek(-10 ** 9)
            prog[key] = {'pos': 0.0, 'done': False}

def pick(scr, title, items, marks=None):
    sel = 0
    scr.timeout(-1)
    while True:
        scr.erase()
        h, w = scr.getmaxyx()
        scr.addnstr(0, 2, title, w - 3, curses.A_BOLD)
        for i, it in enumerate(items[:h - 3]):
            mark = ('  [' + marks[it] + ']') if marks and marks.get(it) else ''
            line = ('> ' if i == sel else '  ') + it + mark
            scr.addnstr(2 + i, 2, line, w - 3, curses.A_REVERSE if i == sel else 0)
        scr.addnstr(h - 1, 2, S['CONTROLS_LIST'], w - 3, curses.A_DIM)
        scr.refresh()
        k = scr.getch()
        if k in (ord('q'), 27):
            return None
        if k == curses.KEY_UP and sel > 0:
            sel -= 1
        elif k == curses.KEY_DOWN and sel < len(items) - 1:
            sel += 1
        elif k in (10, 13, curses.KEY_ENTER) and items:
            return items[sel]

def main(scr):
    curses.curs_set(0)
    prog = P.load_progress()
    lib = P.scan_library()
    if not lib:
        scr.addnstr(1, 2, S['EMPTY'], 70)
        scr.addnstr(3, 2, 'q', 5)
        scr.refresh()
        scr.timeout(-1)
        while scr.getch() not in (ord('q'), 27):
            pass
        return
    pl = P.Player()
    while True:
        pod = pick(scr, S['APP_TITLE'], list(lib))
        if pod is None:
            return
        while True:
            eps = lib[pod]
            names = [os.path.splitext(os.path.basename(e))[0] for e in eps]
            marks = {}
            for e, n in zip(eps, names):
                st = prog.get(P.episode_key(e), {})
                if st.get('done'):
                    marks[n] = S['DONE']
                elif st.get('pos', 0) > 1:
                    marks[n] = S['RESUME'] + ' ' + P.fmt_time(st['pos'])
            choice = pick(scr, pod + ' - ' + S['EPISODES_OF'], names, marks)
            if choice is None:
                break
            run_player(scr, pod, eps[names.index(choice)], pl, prog)

if __name__ == '__main__':
    curses.wrapper(main)
