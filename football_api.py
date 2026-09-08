from datetime import datetime, timezone

import httpx


API_URL = "https://api.football-data.org/v4"

COUNTRY_CODES = {
    "England": "ENG",
    "Spain": "ESP",
    "Germany": "DEU",
    "France": "FRA",
    "Italy": "ITA",
    "Netherlands": "NED",
    "Portugal": "PRT",
    "Türkiye": "TUR",
    "Turkey": "TUR",
    "Ukraine": "UKR",
    "Greece": "GRC",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Norway": "NOR",
    "Azerbaijan": "AZE",
    "Czech Republic": "CZE",
    "Slovakia": "SVK",
    "Scotland": "SCO",
    "Switzerland": "CHE",
}


class FootballApiError(RuntimeError):
    pass


def api_datetime_to_storage(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def get_champions_league_matchday(
    token: str,
    matchday: int,
    season: str | None = None,
) -> list[dict]:
    params = {"matchday": matchday}
    if season and season[:4].isdigit():
        params["season"] = season[:4]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{API_URL}/competitions/CL/matches",
                headers={"X-Auth-Token": token},
                params=params,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise FootballApiError(
            f"API вернул ошибку {error.response.status_code}."
        ) from error
    except httpx.HTTPError as error:
        raise FootballApiError("Не удалось подключиться к футбольному API.") from error

    payload = response.json()
    matches = payload.get("matches")
    if not isinstance(matches, list):
        raise FootballApiError("API вернул неожиданный формат данных.")

    result = []
    for match in matches:
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        kickoff = match.get("utcDate")
        if not home.get("name") or not away.get("name") or not kickoff:
            continue
        full_time = (match.get("score") or {}).get("fullTime") or {}
        result.append(
            {
                "match_number": len(result) + 1,
                "home_team": home.get("shortName") or home["name"],
                "away_team": away.get("shortName") or away["name"],
                "home_logo_url": home.get("crest"),
                "away_logo_url": away.get("crest"),
                "home_country_code": (home.get("area") or {}).get("countryCode")
                or COUNTRY_CODES.get((home.get("area") or {}).get("name")),
                "away_country_code": (away.get("area") or {}).get("countryCode")
                or COUNTRY_CODES.get((away.get("area") or {}).get("name")),
                "kickoff_at": api_datetime_to_storage(kickoff),
                "result_home": full_time.get("home"),
                "result_away": full_time.get("away"),
            }
        )
    return result