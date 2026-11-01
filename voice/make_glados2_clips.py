"""Фрагменты голоса «GLaDOS» для voice/: модель TeraTTS/glados2-g2p-vits из пакета RUTTS, тексты — CLIPS из make_clips.py, HI и RIDE ниже.

Запуск (Python 3.11 — у RUTTS старый transformers без сборок под 3.12+; пакеты RUTTS soundfile):
    C:\\Users\\misha\\venvs\\rutts\\Scripts\\python.exe make_glados2_clips.py   [--force] [--check]
--check — только показать фонемы каждого фрагмента (o1 — ударная, o0 — безударная), без синтеза.
Результат: snd/glados2/<ключ>.mp3.

Ударения: у модели словарь на 2 млн слов. Слово с «+» перед ударной гласной (прив+ет) мимо словаря идёт как написано,
без «+» все гласные безударные. У омографов словарь берёт последний вариант — неверные правим в WORDS/STRESS.
«текст [0.4] текст» — части синтезируются отдельно и склеиваются через паузу в секундах."""
import os, re, sys
if not sys.flags.utf8_mode:   # RUTTS читает словарь без encoding: на Windows (cp1251) не находит ни слова → «наль» вместо «ноль»
    import subprocess; sys.exit(subprocess.call([sys.executable, '-X', 'utf8', *sys.argv]))
import numpy as np, soundfile as sf
from RUTTS import TTS

HERE = os.path.dirname(os.path.abspath(__file__))
c = {'re': re}
src = open(os.path.join(HERE, 'make_clips.py'), encoding='utf-8').read()
exec(src[src.index('\nU = '):src.index('async def one')], c)   # только CLIPS, без импорта edge_tts
CLIPS = c['CLIPS']
HI = {   # приветствия при выборе голоса (hi у glados в VOICES в index.html), выпадает случайное
    'hi_glados1': 'Голосовой модуль активирован. Начинаем испытание. Постарайся не разочаровать меня сразу.',
    'hi_glados2': 'Привет. Я буду считать твои круги. Все. Даже медленные. Особенно медленные.',
    'hi_glados3': 'Хронометраж готов. Испытуемый — условно готов.',
    'hi_glados4': 'Ты выбрал меня. Разумное решение. Первое за сегодня.',
}
RIDE = {   # фразы GLaDOS для езды — только для неё; когда звучат, пользователь напишет позже (в index.html пока не подключены)
    'gl_cake': 'Побьёшь свой лучший круг — получишь торт. Это не обещание. Это мотивационная конструкция.',
    'gl_helmet': 'Шлем надет? Хорошо. Наличие мозга внутри шлема проверить не могу.',
    'gl_bones': 'Добро пожаловать, мешок с костями. Постарайся вернуться с трассы в том же количестве частей, в каком выехал.',
    'gl_brake': 'Голос GLaDOS активирован. Теперь каждое твоё торможение будет оценено. Беспристрастно. Почти.',
}
CLIPS = {**CLIPS, **HI, **RIDE}
WORDS = {              # слово → как читать во всех фрагментах (омографы, где словарь выбирает не тот вариант)
    'шесть': 'ш+есть', 'две': 'дв+е',
    'пятьдесят': 'пятьдес+ят', 'шестьдесят': 'шестьдес+ят', 'семьдесят': 'с+емьдесят', 'восемьдесят': 'в+осемьдесят',
}
STRESS = {             # ключ → текст целиком
    'report2': 'Их никт+о неув+идит.',   # «не» в словаре — «нё»; слитно читается безударным, как в речи
    'watch': 'Слеж+у зак+артом',         # «за» в словаре ударное
    'hi_glados1': 'Голосовой модуль активирован. Начинаем испытание. Постарайся неразочаров+ать меня сразу.',
    'hi_glados2': 'Привет. Я буду считать твои круги. Вс+е. Даже медленные. Особенно медленные.',   # словарь: «всё»
    'hi_glados3': 'Хронометраж гот+ов. Испытуемый — [0.4] условно гот+ов.',                        # словарь: «г+отов»; у тире модель держит всего 0.1 с
    'hi_glados4': 'Ты выбрал меня. Разумное решение. Первое засев+одня.',                           # «за» ударное, «сегодня» читается через «г»
    'gl_cake': 'Побьёшь свой лучший круг — получишь т+оррт. Это необещ+ание. Это мотивационная конструкция.',   # «не» — «нё»; «торт» модель глотает до «тот» — двойная «р»
    'gl_helmet': 'Шлем надет? Хорошо. Наличие мозга внутри шл+ема проверить немог+у.',                       # словарь: «шлёма», «нё»
    'gl_bones': 'Добр+о пожаловать, мешок с костями. Постарайся вернуться с трассы в том же количестве частей, в каком выехал.',   # словарь: «д+обро»
    'gl_brake': 'Голос Гл+адос активирован. Теп+ерь, каждое твоё торможение будет оц+енено. Беспристрастно. Почтт+и.',   # латиница модели незнакома; «оценен+о»; без запятой «тепе», без двойной «т» «почи»
}
SCALE = 0.826          # lenght_scale (так в библиотеке): >1 медленнее; 1.1 — «ноль» тянулся в «ноаль», 0.826 — в 1.15 раза быстрее 0.95 (выбор пользователя)
NOISE, NOISE_W = 0.33, 0.5   # «дрожь» звука и длительностей; у RUTTS 0.667/0.8 зашиты — ровнее звучит с меньшими (выбрал пользователь)
TARGET_RMS = 0.14      # громкость речи как у фрагментов Светланы (медиана по snd/svetlana)
SR = 22050             # модель всегда отдаёт 22050 Гц
MODELS = os.environ.get('RUTTS_MODELS', os.path.expanduser('~/venvs/rutts-models'))   # иначе RUTTS качает модель в ./model
FORCE, CHECK = '--force' in sys.argv, '--check' in sys.argv
ONLY = [a for a in sys.argv[1:] if not a.startswith('--')]   # ключи: пересоздать только их
PAUSE = re.compile(r'\s*\[(\d+(?:\.\d+)?)\]\s*')
SMOOTH = 8   # фразы RIDE синтезируются столько раз, берётся прогон с самым ровным тоном: у модели бывают «вскрики» (скачок на октаву)

def text_for(k):
    return STRESS.get(k) or re.sub(r'[а-яё]+', lambda m: WORDS.get(m[0].lower(), m[0]), CLIPS[k], flags=re.I)

def synth(tts, text):   # как TTS.__call__, но со своими NOISE/NOISE_W
    ids = np.expand_dims(np.array(tts._get_seq(text), dtype=np.int64), 0)
    return tts.model.run(None, {'input': ids, 'input_lengths': np.array([ids.shape[1]], dtype=np.int64),
                                'scales': np.array([NOISE, SCALE, NOISE_W], dtype=np.float32), 'sid': None})[0][0, 0][0]

def render(tts, text):
    parts, out = PAUSE.split(text), []
    for i, p in enumerate(parts):
        if i % 2: out.append(np.zeros(int(float(p) * SR), np.float32))
        elif p.strip(): out.append(trim(np.asarray(synth(tts, p), dtype=np.float32).ravel(), SR))
    return np.concatenate(out)

def jump(x, n=int(.04 * SR), step=int(.0125 * SR)):   # самый резкий скачок тона между соседними кадрами, в полутонах
    f = []
    for i in range(0, len(x) - n, step):
        fr = x[i:i+n] - x[i:i+n].mean()
        if np.sqrt(np.mean(fr ** 2)) < 0.02: f.append(0); continue
        ac = np.correlate(fr, fr, 'full')[n-1:]; lo, hi = int(SR / 500), int(SR / 70)
        k = lo + np.argmax(ac[lo:hi]); f.append(SR / k if ac[k] > 0.3 * ac[0] else 0)
    return max((abs(12 * np.log2(b / a)) for a, b in zip(f, f[1:]) if a and b), default=0)

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
    if CHECK:
        for k in ONLY or CLIPS: print(f'{k:8} {text_for(k):40} {" | ".join(" ".join(tts.tokenizer.g2p(p)[1]) for p in PAUSE.split(text_for(k))[::2])}')
        return
    for k in ONLY or CLIPS:
        path = os.path.join(out, k + '.mp3')
        if os.path.exists(path) and not (FORCE or ONLY): continue
        runs = [trim(render(tts, text_for(k)), SR) for _ in range(SMOOTH if k in RIDE else 1)]
        y = level(min(runs, key=jump))
        sf.write(path, y.astype(np.float32), SR, format='MP3')
        print(k, end=' ', flush=True)
    print('\nok', len(CLIPS))

main()
