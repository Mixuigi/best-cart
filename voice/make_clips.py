"""Генерирует аудиофрагменты для «Голоса круга» нейроголосами Microsoft Edge (пакет edge-tts).

Запуск:  pip install edge-tts  &&  python make_clips.py
Результат: snd/<voice>/<key>.mp3. Ключи должны совпадать с CLIP_TEXT в index.html.
"""
import asyncio, os
import edge_tts

VOICES = {'svetlana': 'ru-RU-SvetlanaNeural', 'dmitry': 'ru-RU-DmitryNeural'}
RATE = '+5%'

U = ['ноль','один','два','три','четыре','пять','шесть','семь','восемь','девять','десять','одиннадцать','двенадцать',
     'тринадцать','четырнадцать','пятнадцать','шестнадцать','семнадцать','восемнадцать','девятнадцать']
T = ['','','двадцать','тридцать','сорок','пятьдесят','шестьдесят','семьдесят','восемьдесят','девяносто']

def words(n):
    return U[n] if n < 20 else T[n // 10] + (' ' + U[n % 10] if n % 10 else '')

CLIPS = {f'n{i}': words(i) for i in range(100)}
CLIPS.update({f'z{i}': 'ноль ' + U[i] for i in range(10)})
CLIPS.update({
    'f1': 'одна', 'f2': 'две',
    'leader': 'Лидер:', 'pos': 'Позиция', 'best': 'Лучший!', 'youlead': 'Ты лидер!',
    'lost': 'Нет связи с таймингом.', 'back': 'Связь с таймингом есть.',
    'watch': 'Слежу за картом', 'seen': 'Вижу карт', 'nolaps': 'Кругов пока нет.', 'setnum': 'Укажи номер карта.',
})

async def one(sem, voice, key, text, out):
    path = os.path.join(out, key + '.mp3')
    if os.path.exists(path): return
    async with sem:
        for attempt in range(4):
            try:
                await edge_tts.Communicate(text, voice, rate=RATE).save(path)
                return
            except Exception as e:
                if attempt == 3: raise
                await asyncio.sleep(1 + attempt)

async def main():
    sem = asyncio.Semaphore(6)
    here = os.path.dirname(os.path.abspath(__file__))
    jobs = []
    for name, voice in VOICES.items():
        out = os.path.join(here, 'snd', name); os.makedirs(out, exist_ok=True)
        jobs += [one(sem, voice, k, t, out) for k, t in CLIPS.items()]
    await asyncio.gather(*jobs)
    print('ok', len(jobs))

asyncio.run(main())
