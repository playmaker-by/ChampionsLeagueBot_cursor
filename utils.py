from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import TIMEZONE


KICKOFF_STORAGE_FORMAT = "%Y-%m-%d %H:%M:%S"
KICKOFF_INPUT_FORMAT = "%d.%m.%Y %H:%M"
KICKOFF_DISPLAY_FORMAT = "%d.%m %H:%M"


TEAM_FLAGS = {
    "arsenal": "🇬🇧",
    "арсенал": "🇬🇧",
    "manchester city": "🇬🇧",
    "манчестер сити": "🇬🇧",
    "manchester united": "🇬🇧",
    "манчестер юнайтед": "🇬🇧",
    "liverpool": "🇬🇧",
    "ливерпуль": "🇬🇧",
    "chelsea": "🇬🇧",
    "челси": "🇬🇧",
    "tottenham": "🇬🇧",
    "тоттенхэм": "🇬🇧",
    "real madrid": "🇪🇸",
    "реал мадрид": "🇪🇸",
    "barcelona": "🇪🇸",
    "барселона": "🇪🇸",
    "atletico de madrid": "🇪🇸",
    "атлетико": "🇪🇸",
    "benfica": "🇵🇹",
    "бенфика": "🇵🇹",
    "porto": "🇵🇹",
    "порту": "🇵🇹",
    "sporting cp": "🇵🇹",
    "спортинг": "🇵🇹",
    "bayern munich": "🇩🇪",
    "бавария": "🇩🇪",
    "borussia dortmund": "🇩🇪",
    "боруссия дортмунд": "🇩🇪",
    "bayer leverkusen": "🇩🇪",
    "байер": "🇩🇪",
    "paris saint-germain": "🇫🇷",
    "псж": "🇫🇷",
    "marseille": "🇫🇷",
    "марсель": "🇫🇷",
    "inter milan": "🇮🇹",
    "интер": "🇮🇹",
    "ac milan": "🇮🇹",
    "милан": "🇮🇹",
    "juventus": "🇮🇹",
    "ювентус": "🇮🇹",
    "napoli": "🇮🇹",
    "наполи": "🇮🇹",
    "ajax": "🇳🇱",
    "аякс": "🇳🇱",
    "psv": "🇳🇱",
    "псв": "🇳🇱",
    "feyenoord": "🇳🇱",
    "фейеноорд": "🇳🇱",
    "аек афины": "🇬🇷",
    "олимпиакос": "🇬🇷",
    "ласк": "🇦🇹",
    "галатасарай": "🇹🇷",
    "шахтер": "🇺🇦",
}


TEAM_NAMES_RU = {
    "aek athens fc": "АЕК Афины",
    "arsenal": "Арсенал",
    "aston villa": "Астон Вилла",
    "atletico madrid": "Атлетико Мадрид",
    "manchester city": "Манчестер Сити",
    "manchester united": "Манчестер Юнайтед",
    "liverpool": "Ливерпуль",
    "chelsea": "Челси",
    "tottenham": "Тоттенхэм",
    "real madrid": "Реал Мадрид",
    "barcelona": "Барселона",
    "atletico de madrid": "Атлетико Мадрид",
    "bayern münchen": "Бавария",
    "benfica": "Бенфика",
    "bodo/glimt": "Буде-Глимт",
    "porto": "Порту",
    "fc porto": "Порту",
    "sporting cp": "Спортинг",
    "bayern munich": "Бавария",
    "borussia dortmund": "Боруссия Дортмунд",
    "club bruges kv": "Брюгге",
    "bayer leverkusen": "Байер",
    "como": "Комо",
    "fenerbahçe": "Фенербахче",
    "feyenoord": "Фейеноорд",
    "galatasaray": "Галатасарай",
    "paris saint-germain": "ПСЖ",
    "paris saint germain": "Пари Сен-Жермен",
    "marseille": "Марсель",
    "inter milan": "Интер",
    "inter": "Интер",
    "ac milan": "Милан",
    "juventus": "Ювентус",
    "napoli": "Наполи",
    "ajax": "Аякс",
    "psv": "ПСВ",
    "lask linz": "ЛАСК",
    "rb leipzig": "Лейпциг",
    "lens": "Ланс",
    "lille": "Лилль",
    "real betis": "Бетис",
    "as roma": "Рома",
    "sabah fa": "Сабах",
    "shakhtar donetsk": "Шахтер",
    "slavia praha": "Славия Прага",
    "slovan bratislava": "Слован Братислава",
    "vfb stuttgart": "Штутгарт",
    "viking": "Викинг",
    "villarreal": "Вильяреал",
}

COUNTRY_FLAGS = {
    "AUT": "🇦🇹",
    "BEL": "🇧🇪",
    "CHE": "🇨🇭",
    "DEU": "🇩🇪",
    "ENG": "🇬🇧",
    "ESP": "🇪🇸",
    "FRA": "🇫🇷",
    "GRE": "🇬🇷",
    "GRC": "🇬🇷",
    "ITA": "🇮🇹",
    "NED": "🇳🇱",
    "NOR": "🇳🇴",
    "POR": "🇵🇹",
    "PRT": "🇵🇹",
    "SCO": "🏴", 
    "TUR": "🇹🇷",
    "UKR": "🇺🇦",
    "AZE": "🇦🇿",
    "CZE": "🇨🇿",
    "SVK": "🇸🇰",
}


class ParseError(ValueError):
    pass


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime(KICKOFF_STORAGE_FORMAT)


def convert_to_utc(date_time_text: str) -> str:
    local_datetime = datetime.strptime(
        date_time_text,
        KICKOFF_INPUT_FORMAT,
    )
    local_datetime = local_datetime.replace(
        tzinfo=ZoneInfo(TIMEZONE)
    )
    utc_datetime = local_datetime.astimezone(timezone.utc)
    return utc_datetime.strftime(KICKOFF_STORAGE_FORMAT)


def parse_kickoff_utc(kickoff_at: str) -> datetime:
    return datetime.strptime(
        kickoff_at,
        KICKOFF_STORAGE_FORMAT,
    ).replace(tzinfo=timezone.utc)


def format_kickoff_local(kickoff_at: str) -> str:
    local_datetime = parse_kickoff_utc(kickoff_at).astimezone(
        ZoneInfo(TIMEZONE)
    )
    return local_datetime.strftime(KICKOFF_INPUT_FORMAT)


def format_kickoff_compact(kickoff_at: str) -> str:
    local_datetime = parse_kickoff_utc(kickoff_at).astimezone(
        ZoneInfo(TIMEZONE)
    )
    return local_datetime.strftime(KICKOFF_DISPLAY_FORMAT)


def format_team_name(
    team_name: str,
    display_name: str | None = None,
    country_code: str | None = None,
    flag_emoji: str | None = None,
) -> str:
    normalized = team_name.strip().casefold()
    localized_name = display_name or TEAM_NAMES_RU.get(normalized, team_name)
    flag = (
        flag_emoji
        or COUNTRY_FLAGS.get((country_code or "").upper())
        or TEAM_FLAGS.get(normalized)
        or TEAM_FLAGS.get(localized_name.casefold())
    )
    return f"{flag} {localized_name}" if flag else localized_name


def format_match_teams(
    home_team: str,
    away_team: str,
    home_display_name: str | None = None,
    away_display_name: str | None = None,
    home_country_code: str | None = None,
    away_country_code: str | None = None,
    home_flag_emoji: str | None = None,
    away_flag_emoji: str | None = None,
) -> str:
    return (
        f"{format_team_name(home_team, home_display_name, home_country_code, home_flag_emoji)}"
        " — "
        f"{format_team_name(away_team, away_display_name, away_country_code, away_flag_emoji)}"
    )


def match_has_started(kickoff_at: str) -> bool:
    return datetime.now(timezone.utc) >= parse_kickoff_utc(kickoff_at)


def parse_match_line(line: str) -> dict:
    parts = [part.strip() for part in line.split("|")]

    if len(parts) != 4:
        raise ParseError(
            "Нужен формат:\nномер|дата время|хозяева|гости"
        )

    match_number_text, date_time_text, home_team, away_team = parts

    try:
        match_number = int(match_number_text)
    except ValueError as error:
        raise ParseError("Номер матча должен быть числом.") from error

    if match_number < 1 or match_number > 18:
        raise ParseError("Номер матча должен быть от 1 до 18.")

    try:
        kickoff_utc = convert_to_utc(date_time_text)
    except ValueError as error:
        raise ParseError(
            "Дата и время должны быть в формате:\n"
            "ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
            "Например:\n08.09.2026 21:00"
        ) from error

    if not home_team or not away_team:
        raise ParseError("Названия команд не могут быть пустыми.")

    if home_team == away_team:
        raise ParseError(
            "Хозяева и гости не могут быть одной и той же командой."
        )

    return {
        "match_number": match_number,
        "home_team": home_team,
        "away_team": away_team,
        "kickoff_utc": kickoff_utc,
        "date_time_text": date_time_text,
    }


def parse_score(text: str) -> tuple[int, int]:
    cleaned = text.strip().replace(" ", "")
    for separator in (":", "-", "–", "—"):
        if separator in cleaned:
            left, right = cleaned.split(separator, 1)
            break
    else:
        raise ParseError("Нужен счёт в формате 2:1 или 2-1.")

    try:
        home_score = int(left)
        away_score = int(right)
    except ValueError as error:
        raise ParseError("Счёт должен быть целыми числами, например 2:1.") from error

    if home_score < 0 or away_score < 0:
        raise ParseError("Счёт не может быть отрицательным.")

    return home_score, away_score


def display_name(row) -> str:
    parts = [
        (row["first_name"] or "").strip(),
        (row["last_name"] or "").strip(),
    ]
    name = " ".join(part for part in parts if part)
    username = (row["username"] or "").strip()

    if name and username:
        return f"{name} (@{username})"
    if name:
        return name
    if username:
        return f"@{username}"
    return f"id{row['telegram_id']}"


def chunk_text(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks = []
    current = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        if current_len + len(line) > limit and current:
            chunks.append("".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line)

    if current:
        chunks.append("".join(current))

    return chunks
