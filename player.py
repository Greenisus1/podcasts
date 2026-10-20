"""Playback engine: wav info, trimming, progress store, and an aplay-backed
player with pause/seek. Audio output runs through aplay (ALSA, preinstalled on
DietPi); everything is injectable so tests need no sound hardware."""
import json, os, re, signal, subprocess, tempfile, threading, time, wave

APP_DIR = os.environ.get('PODCASTS_DIR') or os.path.join(os.path.expanduser('~'), 'podcasts')
PROGRESS_FILE = os.environ.get('PODCASTS_PROGRESS') or os.path.join(APP_DIR, '.progress.json')
SEEK_STEP = 10

def fmt_time(seconds):
    seconds = max(0, int(seconds))
    return '%d:%02d' % divmod(seconds, 60) if seconds < 3600 else '%d:%02d:%02d' % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)

def wav_info(path):
    """(seconds, channels, rate, width) of a wav file."""
    with wave.open(path, 'rb') as w:
        return w.getnframes() / float(w.getframerate()), w.getnchannels(), w.getframerate(), w.getsampwidth()

def trim_wav(src, seconds, dst):
    """Copy src wav starting at <seconds> into dst. Returns seconds actually skipped."""
    with wave.open(src, 'rb') as w:
        params = w.getparams()
        rate = w.getframerate()
        start = min(w.getnframes(), int(seconds * rate))
        w.setpos(start)
        frames = w.readframes(w.getnframes() - start)
    with wave.open(dst, 'wb') as o:
        o.setparams(params)
        o.writeframes(frames)
    return start / float(rate)

def safe_episode_name(name):
    return re.sub(r'[^A-Za-z0-9 _.-]+', '', name).strip() or 'episode'

def scan_library(root=None):
    """{podcast: [episode paths sorted]} for folders of .wav files."""
    root = root or APP_DIR
    lib = {}
    try:
        pods = sorted(os.listdir(root))
    except OSError:
        return lib
    for pod in pods:
        d = os.path.join(root, pod)
        if not os.path.isdir(d):
            continue
        eps = sorted(f for f in os.listdir(d) if f.lower().endswith('.wav'))
        if eps:
            lib[pod] = [os.path.join(d, f) for f in eps]
    return lib

def load_progress(path=None):
    try:
        with open(path or PROGRESS_FILE) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_progress(prog, path=None):
    path = path or PROGRESS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(prog, fh, indent=1)
    os.replace(tmp, path)

def episode_key(path):
    return os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path))

class Player:
    """One aplay child at a time. pause = SIGSTOP, seek = restart from a trimmed wav.
    spawner(cmd) -> process-like object is injectable for tests."""
    def __init__(self, spawner=None, sleeper=time.sleep):
        self.spawner = spawner or (lambda cmd: subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        self.proc = None
        self.path = None
        self.duration = 0.0
        self.base = 0.0          # wav offset the current child started at
        self.started = 0.0       # wall time the current child (re)started
        self.paused = False
        self._tmp = None
        self._lock = threading.Lock()

    def play(self, path, position=0.0):
        with self._lock:
            self.stop_locked()
            self.path = path
            try:
                self.duration = wav_info(path)[0]
            except Exception:
                self.duration = 0.0
            self._spawn_locked(max(0.0, min(position, max(0.0, self.duration - 0.5))))
        return self.position()

    def _spawn_locked(self, offset):
        self._cleanup_tmp()
        src = self.path
        if offset > 0.5:
            fd, self._tmp = tempfile.mkstemp(suffix='.wav', prefix='podcasts-')
            os.close(fd)
            offset = trim_wav(self.path, offset, self._tmp)
            src = self._tmp
        self.proc = self.spawner(['aplay', '-q', src])
        self.base = offset
        self.started = time.monotonic()
        self.paused = False

    def _cleanup_tmp(self):
        if self._tmp and os.path.exists(self._tmp):
            try: os.unlink(self._tmp)
            except OSError: pass
        self._tmp = None

    def position(self):
        if self.proc is None:
            return self.base
        pos = self.base if self.paused else self.base + (time.monotonic() - self.started)
        return min(pos, self.duration) if self.duration else pos

    def playing(self):
        return self.proc is not None and not self.paused and self.proc.poll() is None

    def finished(self):
        return self.proc is not None and self.proc.poll() is not None and not self.paused

    def pause(self):
        with self._lock:
            if self.proc is None or self.paused:
                return self.position()
            self.base = self.position()
            try: os.kill(self.proc.pid, signal.SIGSTOP)
            except Exception: pass
            self.paused = True
            return self.base

    def resume(self):
        with self._lock:
            if self.proc is None or not self.paused:
                return self.position()
            try: os.kill(self.proc.pid, signal.SIGCONT)
            except Exception: pass
            self.started = time.monotonic()
            self.paused = False
            return self.position()

    def toggle(self):
        return self.resume() if self.paused else self.pause()

    def seek(self, delta):
        with self._lock:
            if self.path is None:
                return 0.0
            target = max(0.0, min(self.position() + delta, max(0.0, self.duration - 0.5)))
            was_paused = self.paused
            if self.proc is not None:
                try: self.proc.kill()
                except Exception: pass
                self.proc = None
            self._spawn_locked(target)
            if was_paused:
                self.base = target
                try: os.kill(self.proc.pid, signal.SIGSTOP)
                except Exception: pass
                self.paused = True
            return target

    def stop_locked(self):
        if self.proc is not None:
            try: self.proc.kill()
            except Exception: pass
            self.proc = None
        self._cleanup_tmp()

    def stop(self):
        with self._lock:
            pos = self.position()
            self.stop_locked()
            return pos
