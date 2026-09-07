from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import TIMEZONE


KICKOFF_STORAGE_FORMAT = "%Y-%m-%d %H:%M:%S"
KICKOFF_INPUT_FORMAT = "%d.%m.%Y %H:%M"
KICKOFF_DISPLAY_FORMAT = "%d.%m %H:%M"


TEAM_FLAGS = {
    "арсенал": "🇬🇧",
    "манчестер сити": "🇬🇧",
    "манчестер юнайтед": "🇬🇧",
    "ливерпуль": "🇬🇧",
    "челси": "🇬🇧",
    "тоттенхэм": "🇬🇧",
    "реал мадрид": "🇪🇸",
    "барселона": "🇪🇸",
    "атлетико": "🇪🇸",
    "бенфика": "🇵🇹",
    "порту": "🇵🇹",
    "спортинг": "🇵🇹",
    "бавария": "🇩🇪",
    "боруссия дортмунд": "🇩🇪",
    "байер": "🇩🇪",
    "псж": "🇫🇷",
    "марсель": "🇫🇷",
    "интер": "🇮🇹",
    "милан": "🇮🇹",
    "ювентус": "🇮🇹",
    "наполи": "🇮🇹",
    "аякс": "🇳🇱",
    "псв": "🇳🇱",
    "фейеноорд": "🇳🇱",
    "аек афины": "🇬🇷",
    "олимпиакос": "🇬🇷",
    "ласк": "🇦🇹",
    "галатасарай": "🇹🇷",
    "шахтер": "🇺🇦",
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


def format_team_name(team_name: str) -> str:
    flag = TEAM_FLAGS.get(team_name.casefold())
    return f"{flag} {team_name}" if flag else team_name


def format_match_teams(home_team: str, away_team: str) -> str:
    return f"{format_team_name(home_team)} — {format_team_name(away_team)}"


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
