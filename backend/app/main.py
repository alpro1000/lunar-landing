from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from zoneinfo import ZoneInfo

SYNODIC = 29.530588853
REF = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
PHASE_BREAKPOINTS = [1.84566, 5.53699, 9.22831, 12.91963, 16.61096, 20.30228, 23.99361, 27.68493]
PHASE_LABELS = {
    "en": {
        "New": "New Moon",
        "WaxingCrescent": "Waxing Crescent",
        "FirstQuarter": "First Quarter",
        "WaxingGibbous": "Waxing Gibbous",
        "Full": "Full Moon",
        "WaningGibbous": "Waning Gibbous",
        "LastQuarter": "Last Quarter",
        "WaningCrescent": "Waning Crescent",
    },
    "ru": {
        "New": "Новолуние",
        "WaxingCrescent": "Растущий серп",
        "FirstQuarter": "Первая четверть",
        "WaxingGibbous": "Растущая выпуклая",
        "Full": "Полнолуние",
        "WaningGibbous": "Убывающая выпуклая",
        "LastQuarter": "Последняя четверть",
        "WaningCrescent": "Убывающий серп",
    },
}

DAY_TABLES: Dict[str, Dict[int, Dict[str, str]]] = {
    "en": {
        1: {"description": "No fixed category", "recommendation": "Set intentions; observe dreams as a compass."},
        2: {"description": "No separate label", "recommendation": "Generosity and planning support clarity."},
        3: {"description": "Testing, likely to materialize", "recommendation": "Overcoming obstacles hints at real-world trials."},
        4: {"description": "Cautionary and ancestral", "recommendation": "Family themes require attention."},
        5: {"description": "Neutral-positive", "recommendation": "Enjoy the favorable backdrop."},
        6: {"description": "Anticipatory and intuitive", "recommendation": "Journal subtle insights and emotional tone."},
        7: {"description": "Highly informative", "recommendation": "Document details; dreams tend to manifest."},
        8: {"description": "Prophetic about vocation", "recommendation": "Look for callings and long arcs."},
        9: {"description": "Tense day", "recommendation": "Ground yourself; keep notes practical."},
        10: {"description": "Mostly empty", "recommendation": "Observe but avoid overinterpretation."},
        11: {"description": "Marker for tomorrow", "recommendation": "Prepare for lunar day 12 to deepen."},
        12: {"description": "Bright and fulfilled", "recommendation": "Celebrate uplifting themes."},
        13: {"description": "Insights and pointers", "recommendation": "Follow the momentum into tomorrow."},
        14: {"description": "Emotional discharge", "recommendation": "Let unpleasant scenes release tension."},
        15: {"description": "Warnings", "recommendation": "Stay aware, but dreams lack strict type."},
        16: {"description": "Cleansing", "recommendation": "Support rituals of release."},
        17: {"description": "Neutral work-like", "recommendation": "Focus on routines without pressure."},
        18: {"description": "Energetic", "recommendation": "Good for power and light practices."},
        19: {"description": "Mostly non-informative", "recommendation": "Rest the analytic mind."},
        20: {"description": "Willpower focus", "recommendation": "Channel determination."},
        21: {"description": "Restorative", "recommendation": "Prioritize recovery and body care."},
        22: {"description": "Knowledge-bearing", "recommendation": "Expect practical guidance."},
        23: {"description": "Inverted", "recommendation": "Interpret dreams in reverse with context."},
        24: {"description": "Diagnostic", "recommendation": "Check-in with your body."},
        25: {"description": "Quiet", "recommendation": "Allow for silence and reset."},
        26: {"description": "Self-esteem", "recommendation": "Practice self-compassion."},
        27: {"description": "Intuitive-prophetic", "recommendation": "Capture insights today and tomorrow."},
        28: {"description": "Balanced", "recommendation": "Maintain harmonious routines."},
        29: {"description": "Liminal", "recommendation": "Honor transitions and rituals."},
        30: {"description": "Final prophetic", "recommendation": "Review lessons and celebrate growth."},
    },
    "ru": {
        1: {"description": "Без фиксированной категории", "recommendation": "Формулируйте намерения, трактуйте сны как ориентир."},
        2: {"description": "Без отдельной метки", "recommendation": "Щедрость и планирование поддерживают ясность."},
        3: {"description": "Проверочные", "recommendation": "Преодоление во сне → проверка в реальности."},
        4: {"description": "Предостерегающие, родовые", "recommendation": "Темы семьи требуют внимания."},
        5: {"description": "Нейтрально-позитивные", "recommendation": "Наслаждайтесь благоприятным фоном."},
        6: {"description": "Предвосхищающие", "recommendation": "Записывайте тонкие инсайты и эмоции."},
        7: {"description": "Высокоинформативные", "recommendation": "Фиксируйте детали — сны склонны сбываться."},
        8: {"description": "Пророческие про призвание", "recommendation": "Ищите подсказки о предназначении."},
        9: {"description": "Напряжённый день", "recommendation": "Заземляйтесь, делайте практичные заметки."},
        10: {"description": "В основном пустые", "recommendation": "Наблюдайте без излишней трактовки."},
        11: {"description": "Маркер завтрашнего дня", "recommendation": "Готовьтесь к насыщенному 12-му дню."},
        12: {"description": "Светлые и сбывающиеся", "recommendation": "Отмечайте вдохновляющие сюжеты."},
        13: {"description": "Инсайты", "recommendation": "Несите импульс в следующую ночь."},
        14: {"description": "Эмоциональная разрядка", "recommendation": "Позвольте напряжению выйти."},
        15: {"description": "Предостережения", "recommendation": "Внимательность без жёсткой классификации."},
        16: {"description": "Очистительные", "recommendation": "Поддержите практики освобождения."},
        17: {"description": "Нейтрально-рабочие", "recommendation": "Фокус на рутине без давления."},
        18: {"description": "Энергетические", "recommendation": "Подходят практики силы и света."},
        19: {"description": "Преимущественно неинформативные", "recommendation": "Дайте уму отдохнуть."},
        20: {"description": "Фокус на воле", "recommendation": "Направляйте решимость."},
        21: {"description": "Восстановительные", "recommendation": "Приоритет — забота о теле."},
        22: {"description": "Познавательные", "recommendation": "Ждите прикладных подсказок."},
        23: {"description": "Инверсионные", "recommendation": "Трактуйте с поправкой «наоборот»."},
        24: {"description": "Диагностические", "recommendation": "Прислушайтесь к телу."},
        25: {"description": "Тишина", "recommendation": "Позвольте паузе и перезагрузке."},
        26: {"description": "Про самооценку", "recommendation": "Практикуйте самосострадание."},
        27: {"description": "Интуитивно-пророческие", "recommendation": "Фиксируйте инсайты сегодня и завтра."},
        28: {"description": "Уравновешенные", "recommendation": "Поддерживайте гармоничные ритуалы."},
        29: {"description": "Пограничные", "recommendation": "Чтите переходы и обряды."},
        30: {"description": "Итоговые пророческие", "recommendation": "Подведите итоги, отметьте рост."},
    },
}

SUPPORTED_LOCALES = tuple(DAY_TABLES.keys())


class LunarResponse(BaseModel):
    date: str
    lunar_day: int
    phase: str
    phase_key: str
    description: str
    recommendation: str
    locale: str
    source: Literal['NASA/astral'] = 'NASA/astral'


app = FastAPI(title='ONEIROSCOP-LUNAR API', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def phase_key_from_age(age: float) -> str:
    if age < PHASE_BREAKPOINTS[0] or age >= PHASE_BREAKPOINTS[-1]:
        return 'New'
    if age < PHASE_BREAKPOINTS[1]:
        return 'WaxingCrescent'
    if age < PHASE_BREAKPOINTS[2]:
        return 'FirstQuarter'
    if age < PHASE_BREAKPOINTS[3]:
        return 'WaxingGibbous'
    if age < PHASE_BREAKPOINTS[4]:
        return 'Full'
    if age < PHASE_BREAKPOINTS[5]:
        return 'WaningGibbous'
    if age < PHASE_BREAKPOINTS[6]:
        return 'LastQuarter'
    if age < PHASE_BREAKPOINTS[7]:
        return 'WaningCrescent'
    return 'New'


def moon_age(moment: datetime) -> float:
    days = (moment - REF).total_seconds() / 86_400
    return ((days % SYNODIC) + SYNODIC) % SYNODIC


def lunar_day(age: float) -> int:
    return max(1, min(30, int(age // 1) + 1))


@lru_cache(maxsize=512)
def get_local_noon(date_key: str, tz_name: str) -> datetime:
    year, month, day = map(int, date_key.split('-'))
    zone = ZoneInfo(tz_name)
    local_noon = datetime(year, month, day, 12, 0, tzinfo=zone)
    return local_noon.astimezone(timezone.utc)


@lru_cache(maxsize=1024)
def compute_lunar_day(date_key: str, tz_name: str, locale: str) -> LunarResponse:
    try:
        ZoneInfo(tz_name)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=f'Unsupported timezone: {tz_name}') from exc

    try:
        datetime.strptime(date_key, '%Y-%m-%d')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid date format, expected YYYY-MM-DD') from exc

    locale_key = locale if locale in SUPPORTED_LOCALES else 'en'
    noon_utc = get_local_noon(date_key, tz_name)
    age = moon_age(noon_utc)
    day = lunar_day(age)
    phase_key = phase_key_from_age(age)

    table = DAY_TABLES[locale_key]
    day_data = table[day]

    phase_name = PHASE_LABELS.get(locale_key, PHASE_LABELS['en'])[phase_key]

    return LunarResponse(
        date=date_key,
        lunar_day=day,
        phase=phase_name,
        phase_key=phase_key,
        description=day_data['description'],
        recommendation=day_data['recommendation'],
        locale=locale_key,
    )


@app.get('/lunar', response_model=LunarResponse)
async def get_lunar(
    date: str = Query(..., description='ISO date YYYY-MM-DD'),
    locale: str = Query('en', description='Locale code, e.g. en or ru'),
    tz: Optional[str] = Query(None, description='IANA timezone ID')
) -> LunarResponse:
    tz_name = tz or 'UTC'
    return compute_lunar_day(date, tz_name, locale)
