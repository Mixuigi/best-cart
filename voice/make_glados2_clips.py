"""Фрагменты голоса «GLaDOS» для voice/: модель TeraTTS/glados2-g2p-vits из пакета RUTTS, тексты — CLIPS из make_clips.py.
Старая GLaDOS (Светлана + обработка, make_glados_clips.py) остаётся в snd/glados.

Запуск (Python 3.11 — у RUTTS старый transformers без сборок под 3.12+; пакеты RUTTS soundfile):
    C:\\Users\\misha\\venvs\\rutts\\Scripts\\python.exe make_glados2_clips.py   [--force]
Результат: snd/glados2/<ключ>.mp3. Ударения правятся в STRESS через «+» перед ударной гласной (прив+ет)."""
import os, sys
import numpy as np, soundfile as sf
from RUTTS import TTS

HERE = os.path.dirname(os.path.abspath(__file__))
c = {}
src = open(os.path.join(HERE, 'make_clips.py'), encoding='utf-8').read()
exec(src[src.index('\nU = '):src.index('async def one')], c)   # только CLIPS, без импорта edge_tts
CLIPS = c['CLIPS']
STRESS = {}            # ключ → текст с ударениями, если модель ставит их не туда
SCALE = 1.1            # lenght_scale (так в библиотеке): >1 медленнее
TARGET_RMS = 0.14      # громкость речи как у фрагментов Светланы (медиана по snd/svetlana)
SR = 22050             # модель всегда отдаёт 22050 Гц
MODELS = os.environ.get('RUTTS_MODELS', os.path.expanduser('~/venvs/rutts-models'))   # иначе RUTTS качает модель в ./model
FORCE = '--force' in sys.argv

def trim(x, sr, thr=0.01, pad=0.03):
    idx = np.flatnonzero(np.abs(x) > thr)
    if not len(idx): return x
    a, b = max(0, idx[0] - int(pad * sr)), min(len(x), idx[-1] + int(pad * sr))
    return x[a:b]

def level(x):
    v = x[np.abs(x) > 0.02]                       # громкость по звучащей части, без пауз
    rms = np.sqrt(np.mean(v ** 2)) if len(v) else 1
    y = x * (TARGET_RMS / max(rms, 1e-6))
    peak = np.max(np.abs(y))
    return y * (0.95 / peak) if peak > 0.95 else y

def main():
    out = os.path.join(HERE, 'snd', 'glados2'); os.makedirs(out, exist_ok=True)
    tts = TTS('TeraTTS/glados2-g2p-vits', save_path=MODELS, add_time_to_end=0.0)
    for k, text in CLIPS.items():
        path = os.path.join(out, k + '.mp3')
        if os.path.exists(path) and not FORCE: continue
        x = np.asarray(tts(STRESS.get(k, text), lenght_scale=SCALE), dtype=np.float32).ravel()
        y = level(trim(x, SR))
        sf.write(path, y.astype(np.float32), SR, format='MP3')
        print(k, end=' ', flush=True)
    print('\nok', len(CLIPS))

main()
