"""Голос «ИИ-надзирательницы» (манера в стиле GLaDOS, Portal 2) — версия 3, по замечаниям к версии 1.
Не клон: нейтральный голос Светланы + обработка мелодики, тембра и пространства.

Запуск (Python 3.12, пакеты numpy scipy pyworld miniaudio soundfile edge-tts):
    python glados_style.py <папка-для-wav>

Цепочка:
  фразы TTS по одной, склейка с заданными паузами (перед «колкостью» длиннее)
  → WORLD-анализ → разбивка на слоги по провалам громкости
  → каждый слог на своей ноте сетки A440, шаг 2–5 полутонов, без глайдов, концы фраз ровно/вверх
  → ресинтез → гейт вдохов → металл: дубль +7 центов, 3 мс, только на гласных
  → выравнивание громкости по слогам → EQ (presence +, воздух −) → компрессия → далёкий зал.
"""
import asyncio, os, sys
import numpy as np, miniaudio, pyworld as pw, soundfile as sf, scipy.signal as ss
import edge_tts

OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
FS = 24000
FP = 5.0                                    # шаг кадров WORLD, мс
BASE = 220.0                                # A3
# (фраза, пауза после неё, с) — длинная пауза стоит перед «колкостью» (сравнением с лидером)
PHRASES = [("Одна, ноль четыре, тридцать два.", .33), ("Одна, ноль четыре, тридцать два.", .33),
           ("Твой лучший круг.", .3), ("Позиция два.", 1.0),
           ("Лучший круг лидера:", .25), ("одна, ноль три, сорок один.", 0)]

async def tts(text):
    buf = b''
    async for ch in edge_tts.Communicate(text, 'ru-RU-SvetlanaNeural', rate='-4%').stream():
        if ch['type'] == 'audio': buf += ch['data']
    d = miniaudio.decode(buf, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=FS)
    return np.asarray(d.samples, dtype=np.float64)

def trim(x, th=0.01):
    nz = np.nonzero(np.abs(x) > th)[0]
    return x[max(0, nz[0] - int(.01 * FS)): nz[-1] + int(.03 * FS)]

def shorten_pauses(x, maxp=.4, th=0.008):    # внутренние паузы TTS (на запятых) не длиннее maxp
    q = np.abs(x) > th; out, i, n = [], 0, len(x)
    while i < n:
        if q[i]: out.append(x[i]); i += 1; continue
        j = i
        while j < n and not q[j]: j += 1
        out.extend(x[i:min(j, i + int(maxp * FS))]); i = j
    return np.array(out)

async def source():
    parts = []
    for text, pause in PHRASES:
        x = shorten_pauses(trim(await tts(text)))
        parts += [x, np.zeros(int(pause * FS))]
    return np.concatenate([np.zeros(int(.2 * FS))] + parts + [np.zeros(int(2.7 * FS))])

# ---------- мелодия ----------
def syllables(f0, en):
    """Слоги: озвученные отрезки, длинные режем по провалам громкости (между гласными)."""
    v = f0 > 0; runs, i = [], 0
    while i < len(f0):
        if not v[i]: i += 1; continue
        j = i
        while j < len(f0) and v[j]: j += 1
        runs.append([i, j]); i = j
    # крошечные отрезки (<40 мс) приклеиваем к соседу — иначе «подъезд» на входе в слово
    merged = []
    for r in runs:
        if merged and (r[1] - r[0]) * FP < 40 and r[0] - merged[-1][1] <= 4: merged[-1][1] = r[1]
        elif merged and (merged[-1][1] - merged[-1][0]) * FP < 40 and r[0] - merged[-1][1] <= 4: merged[-1][1] = r[1]
        else: merged.append(r)
    sm = np.convolve(en, np.ones(7) / 7, 'same')     # ~35 мс
    syl = []
    for i, j in merged:
        k = max(1, int(round((j - i) * FP / 190)))
        cuts = []
        if k > 1:
            seg = sm[i:j]
            mins = [m for m in range(3, len(seg) - 3) if seg[m] <= seg[m - 1] and seg[m] <= seg[m + 1]]
            mins.sort(key=lambda m: seg[m])
            for m in mins:
                if len(cuts) == k - 1: break
                if all(abs(m - c) * FP >= 80 for c in cuts) and m * FP >= 70 and (len(seg) - m) * FP >= 70: cuts.append(m)
            if not cuts: cuts = [int(len(seg) * q / k) for q in range(1, k)]
            cuts.sort()
        b = [i] + [i + c for c in cuts] + [j]
        syl += [(b[q], b[q + 1]) for q in range(len(b) - 1)]
    return syl

def melody(f0, en, rng):
    syl = syllables(f0, en)
    new = np.zeros_like(f0); notes = []; note = 0
    # роли слогов во фразе (фраза — до паузы ≥180 мс): «конец» — последний ПОЛНОЦЕННЫЙ слог (≥60 мс);
    # короткие обрывки после него (хвост согласной) берут его ноту, иначе конец фразы «падал» на обрывке
    ns = len(syl); role = ['mid'] * ns; first = 0
    quiet = en < 0.03 * en.max()
    def pause_after(n):                                       # пауза на слух: ≥100 мс тишины до следующего слога
        if n + 1 >= ns: return True
        q = quiet[syl[n][1]:syl[n + 1][0]]; best = run = 0
        for v in q: run = run + 1 if v else 0; best = max(best, run)
        return best * FP >= 100 or (syl[n + 1][0] - syl[n][1]) * FP >= 180
    for n in range(ns):
        if not pause_after(n): continue
        idx = list(range(first, n + 1))
        real = [k for k in idx if (syl[k][1] - syl[k][0]) * FP >= 60] or idx
        role[real[0]] = 'start'
        for k in idx:
            if k < real[0] or k > real[-1]: role[k] = 'tail'
        role[real[-1]] = 'end'                                   # однослоговая фраза — тоже «конец»
        first = n + 1
    for n, (i, j) in enumerate(syl):
        frag = (j - i) * FP < 60
        if role[n] == 'tail' or (frag and notes and role[n] != 'end'):
            note = notes[-1] if notes else 0                     # обрывок — без новой ноты, держит соседа
        elif role[n] == 'end' and notes:
            note = int(min(notes[-1] + rng.choice([0, 1, 2]), 5))   # конец не падает: ровно или +1–2 пт, не выше D4
        elif role[n] == 'start' or not notes:
            note = int(rng.choice([0, 0, 2, -2]))              # вход ступенькой у базы
        else:
            step = int(rng.integers(2, 6))                      # каждый слог — новая нота, шаг 2–5 пт
            down = rng.random() < (0.5 + 0.12 * note)           # тянет обратно к базе, чтобы не уползала
            note = note - step if down else note + step
            if note > 5: note -= 2 * step                       # коридор −4…+5 от A3
            if note < -4: note += 2 * step
            note = int(np.clip(note, -4, 5))
            if notes and abs(note - notes[-1]) < 2: note = notes[-1] + (2 if notes[-1] <= 0 else -2)
            if notes and abs(note - notes[-1]) > 5: note = notes[-1] + 5 * np.sign(note - notes[-1])
        notes.append(note)
        new[i:j] = BASE * 2 ** (note / 12)                      # retune = 0: нота внутри слога стоит
    return new, syl, notes

# ---------- фильтры ----------
def peaking(f0, gain_db, q):
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / FS; al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]; a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return np.array(b) / a[0], np.array(a) / a[0]

def highshelf(f0, gain_db, s=0.7):
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / FS
    al = np.sin(w) / 2 * np.sqrt((A + 1 / A) * (1 / s - 1) + 2); c = np.cos(w)
    b = [A * ((A + 1) + (A - 1) * c + 2 * np.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - 2 * np.sqrt(A) * al)]
    a = [(A + 1) - (A - 1) * c + 2 * np.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - 2 * np.sqrt(A) * al]
    return np.array(b) / a[0], np.array(a) / a[0]

def compress(y, thr_db=-26, ratio=6.0, att=0.002, rel=0.06):
    a1, r1 = np.exp(-1 / (att * FS)), np.exp(-1 / (rel * FS)); e = 0.0; env = np.empty_like(y); ay = np.abs(y)
    for k in range(len(y)):
        c = a1 if ay[k] > e else r1; e = c * e + (1 - c) * ay[k]; env[k] = e
    thr = 10 ** (thr_db / 20)
    return y * np.where(env > thr, (np.maximum(env, 1e-9) / thr) ** (1 / ratio - 1), 1.0)

def smooth(m, ms):
    n = max(1, int(ms / 1000 * FS)); return np.convolve(m, np.ones(n) / n, 'same')

def render(x, hall=True, seed=11):
    rng = np.random.default_rng(seed)
    f0, t = pw.harvest(x, FS, f0_floor=90, f0_ceil=500, frame_period=FP)
    sp = pw.cheaptrick(x, f0, t, FS); ap = pw.d4c(x, f0, t, FS)
    fr = int(FP / 1000 * FS); nfr = min(len(f0), len(x) // fr)
    en = np.array([np.sqrt(np.mean(x[k * fr:(k + 1) * fr] ** 2)) for k in range(nfr)])
    en = np.concatenate([en, np.zeros(len(f0) - nfr)])
    new, syl, notes = melody(f0, en, rng)
    bins = sp.shape[1]; src = np.arange(bins) / 1.02
    sp = np.array([np.interp(src, np.arange(bins), row) for row in sp])
    y = pw.synthesize(new, sp, ap, FS, FP)
    voiced = smooth(np.repeat((new > 0).astype(float), fr)[:len(y)], 6)
    voiced = np.concatenate([voiced, np.zeros(max(0, len(y) - len(voiced)))])
    # металл: дубль +7 центов, 3 мс, тихо и только на гласных (шипящие без гребёнки)
    dbl = pw.synthesize(new * 2 ** (7 / 1200), sp, ap, FS, FP)[:len(y)] * voiced
    d = int(0.003 * FS); y = y + 0.18 * np.concatenate([np.zeros(d), dbl[:len(y) - d]])
    # гейт вдохов: тихие неозвученные участки глушим
    keep = np.concatenate([(f0[:nfr] > 0) | (en[:nfr] > 0.06 * en.max()), np.zeros(len(f0) - nfr, bool)])
    gate = smooth(np.repeat(keep.astype(float), fr), 8)[:len(y)]
    y = y[:len(gate)] * gate
    # выравнивание громкости по слогам: каждый гласный центр к общей медиане (±9 дБ максимум)
    rms = [np.sqrt(np.mean(y[i * fr:j * fr] ** 2)) + 1e-9 for i, j in syl]
    target = np.median(rms); g = np.ones(len(y))
    for (i, j), r in zip(syl, rms):
        g[i * fr:j * fr] = np.clip(target / r, 10 ** (-9 / 20), 10 ** (9 / 20))
    y = y * smooth(g, 15)
    # EQ: срез низа, presence 2.5–5 кГц вверх, «воздух» вниз
    y = ss.lfilter(*ss.butter(2, 140 / (FS / 2), 'high'), y)
    y = ss.lfilter(*peaking(1300, -2.0, 1.0), y)
    y = ss.lfilter(*peaking(3600, 6.5, 0.7), y)
    y = ss.lfilter(*highshelf(7500, -3.0), y)
    y = compress(y / np.max(np.abs(y)))
    y = y / np.max(np.abs(y))
    if hall:   # далёкий бетонный зал: предзадержка 40 мс, хвост ~2–2.5 с, wet 12 %
        L = int(2.4 * FS); ir = rng.standard_normal(L) * np.exp(-np.arange(L) / (0.45 * FS))
        ir = ss.lfilter(*ss.butter(2, 7500 / (FS / 2)), ir); ir = np.concatenate([np.zeros(int(0.04 * FS)), ir])
        wet = ss.fftconvolve(y, ir)[:len(y)]; wet *= np.sqrt(np.mean(y ** 2)) / np.sqrt(np.mean(wet ** 2))
        y = 0.88 * y + 0.12 * wet
    y = np.tanh(1.6 * y / np.max(np.abs(y))) / np.tanh(1.6)
    nf = int(.04 * FS); y[-nf:] *= np.linspace(1, 0, nf)       # fade-out 40 мс, без щелчка
    return y * 0.89, syl, notes

async def main():
    os.makedirs(OUT, exist_ok=True)
    x = await source()
    y, syl, notes = render(x, hall=True)
    sf.write(os.path.join(OUT, '8-glados-v4-hall.wav'), y, FS)
    if '--dry' in sys.argv: sf.write(os.path.join(OUT, '_check-dry.wav'), render(x, hall=False)[0], FS)   # для замеров
    steps = np.abs(np.diff(notes))
    print('слогов', len(notes), '| одинаковых соседних нот', int(np.sum(steps == 0)),
          '| шаг макс', int(steps.max()), '| длина слога медиана %.0f мс' % np.median([(j - i) * FP for i, j in syl]))

asyncio.run(main())
