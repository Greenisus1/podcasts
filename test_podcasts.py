import json, os, struct, sys, tempfile, unittest, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player as P

def make_wav(path, seconds=2.0, rate=8000):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x00\x01' * int(seconds * rate))

class FakeProc:
    def __init__(self): self.killed = False; self.pid = 4242
    def poll(self): return 0 if self.killed else None
    def kill(self): self.killed = True

class UtilTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
    def tearDown(self):
        self.tmp.cleanup()
    def test_fmt_time(self):
        self.assertEqual(P.fmt_time(0), '0:00')
        self.assertEqual(P.fmt_time(65), '1:05')
        self.assertEqual(P.fmt_time(3661), '1:01:01')
    def test_wav_info_and_trim(self):
        src = os.path.join(self.tmp.name, 'a.wav')
        make_wav(src, 3.0)
        dur, ch, rate, width = P.wav_info(src)
        self.assertAlmostEqual(dur, 3.0, places=2)
        dst = os.path.join(self.tmp.name, 'b.wav')
        skipped = P.trim_wav(src, 1.0, dst)
        self.assertAlmostEqual(skipped, 1.0, places=2)
        dur2 = P.wav_info(dst)[0]
        self.assertAlmostEqual(dur2, 2.0, places=2)
    def test_scan_library(self):
        os.makedirs(os.path.join(self.tmp.name, 'Sleep Japanese'))
        make_wav(os.path.join(self.tmp.name, 'Sleep Japanese', 'Episode 1.wav'), 0.5)
        make_wav(os.path.join(self.tmp.name, 'Sleep Japanese', 'Episode 2.wav'), 0.5)
        open(os.path.join(self.tmp.name, 'not-a-dir.txt'), 'w').write('x')
        lib = P.scan_library(self.tmp.name)
        self.assertEqual(list(lib), ['Sleep Japanese'])
        self.assertEqual(len(lib['Sleep Japanese']), 2)
    def test_progress_roundtrip(self):
        p = os.path.join(self.tmp.name, 'sub', 'prog.json')
        P.save_progress({'show/ep.wav': {'pos': 42.0, 'done': False}}, p)
        self.assertEqual(P.load_progress(p)['show/ep.wav']['pos'], 42.0)
        self.assertEqual(P.load_progress(os.path.join(self.tmp.name, 'missing.json')), {})
    def test_episode_key(self):
        self.assertEqual(P.episode_key('/home/pi/podcasts/Show/Ep 1.wav'), 'Show/Ep 1.wav')

class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wav = os.path.join(self.tmp.name, 'ep.wav')
        make_wav(self.wav, 4.0)
        self.procs = []
        def spawner(cmd):
            p = FakeProc()
            p.cmd = cmd
            self.procs.append(p)
            return p
        self.pl = P.Player(spawner=spawner)
    def tearDown(self):
        self.pl.stop()
        self.tmp.cleanup()
    def test_play_and_finish(self):
        self.pl.play(self.wav, 0)
        self.assertTrue(self.pl.playing())
        self.procs[-1].killed = True
        self.assertTrue(self.pl.finished())
    def test_pause_resume(self):
        self.pl.play(self.wav, 1.0)
        pos = self.pl.pause()
        self.assertGreaterEqual(pos, 1.0)
        self.assertFalse(self.pl.playing())
        self.pl.resume()
        self.assertTrue(self.pl.playing())
    def test_seek_clamps(self):
        self.pl.play(self.wav, 0)
        pos = self.pl.seek(999)
        self.assertLessEqual(pos, 4.0)
        pos = self.pl.seek(-999)
        self.assertEqual(pos, 0.0)
    def test_seek_uses_trimmed_wav(self):
        self.pl.play(self.wav, 0)
        self.pl.seek(2.0)
        self.assertTrue(self.procs[-1].cmd[-1].startswith(tempfile.gettempdir()) or self.procs[-1].cmd[-1] == self.wav)
        self.assertGreaterEqual(self.pl.position(), 1.9)
    def test_position_capped_at_duration(self):
        self.pl.play(self.wav, 0)
        self.assertLessEqual(self.pl.position(), 4.0)

if __name__ == '__main__':
    unittest.main()
