"""Фрагменты голоса GLaDOS для voice/: каждый фрагмент из make_clips.py (тот же текст) озвучивается Светланой
и проходит обработку glados_style.py (мелодика ступеньками, EQ, металл, компрессия) — БЕЗ зала:
зал добавляет страница при воспроизведении (fx 'hall'), чтобы хвост тянулся через всю фразу.

Запуск (Python 3.12: numpy scipy pyworld miniaudio soundfile edge-tts):  python make_glados_clips.py
Результат: snd/glados/<ключ>.mp3"""
import asyncio, os, re, sys, zlib
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__))
g = {}
exec(open(os.path.join(HERE, 'glados_style.py'), encoding='utf-8').read().replace('asyncio.run(main())', ''), g)
clips_src = open(os.path.join(HERE, 'make_clips.py'), encoding='utf-8').read()
c = {}
exec(clips_src.split('async def one')[0], c)          # берём только словарь CLIPS
CLIPS = c['CLIPS']

async def main():
    out = os.path.join(HERE, 'snd', 'glados'); os.makedirs(out, exist_ok=True)
    for k, text in CLIPS.items():
        path = os.path.join(out, k + '.mp3')
        if os.path.exists(path): continue
        x = g['trim'](await g['tts'](text))
        x = np.concatenate([np.zeros(int(.15 * g['FS'])), x, np.zeros(int(.15 * g['FS']))])
        y, _, _ = g['render'](x, hall=False, seed=zlib.crc32(k.encode()) % 100000)
        y = g['trim'](y, 0.005)
        sf.write(path, y.astype(np.float32), g['FS'], format='MP3')
        print(k, end=' ', flush=True)
    print('\nok', len(CLIPS))

asyncio.run(main())
