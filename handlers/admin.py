from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from access import (
    format_standings,
    reject_if_not_admin_callback,
    reject_if_not_admin_message,
)
from broadcast import broadcast_chunks
from config import ADMIN_TELEGRAM_ID, FOOTBALL_DATA_API_TOKEN
from database import db
from football_api import FootballApiError, get_champions_league_matchday
from keyboards import admin_keyboard, user_keyboard
from states import (
    AddMatches,
    AddSingleMatch,
    BindGroup,
    CreateTournament,
    EditMatch,
    EnterResult,
)
from utils import (
    ParseError,
    chunk_text,
    format_match_teams,
    format_kickoff_local,
    match_has_started,
    parse_match_line,
    parse_score,
    display_name,
)


router = Router()
router.message.filter(F.from_user.id == ADMIN_TELEGRAM_ID)


@router.message(Command("cancel"))
async def cancel_admin_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.")


def back_button(text: str, callback_data: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data=callback_data)]


async def send_or_edit(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    *,
    answer: bool = True,
):
    if answer:
        try:
            await callback.answer()
        except Exception:
            pass
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------

def tournaments_keyboard(tournaments) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"🏆 {item['name']} ({item['season']})",
                callback_data=f"adm:t:{item['id']}",
            )
        ]
        for item in tournaments
    ]
    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ Создать турнир",
                callback_data="adm:t:create",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tournaments_text(tournaments) -> str:
    if not tournaments:
        return "🏆 Управление турнирами\n\nТурниров пока нет."

    text = "🏆 Управление турнирами\n\n"
    for tournament in tournaments:
        text += (
            f"• {tournament['name']} — {tournament['season']}\n"
            f"  Статус: {tournament['status']}\n"
            f"  Туров: {tournament['total_rounds']}\n\n"
        )
    return text


async def show_tournaments(target: Message | CallbackQuery):
    tournaments = await db.get_tournaments()
    text = tournaments_text(tournaments)
    keyboard = tournaments_keyboard(tournaments)

    if isinstance(target, CallbackQuery):
        await send_or_edit(target, text, keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


@router.message(Command("admin"))
async def admin_handler(message: Message, state: FSMContext):
    if await reject_if_not_admin_message(message):
        await message.answer("⛔ У тебя нет доступа к панели администратора.")
        return

    await state.clear()
    await message.answer(
        "🔐 Панель администратора\n\nВыбери нужный раздел:",
        reply_markup=admin_keyboard(),
    )


@router.message(F.text == "👤 Меню игрока")
async def admin_to_user_menu(message: Message):
    if await reject_if_not_admin_message(message):
        return
    await message.answer(
        "Открыто меню игрока.",
        reply_markup=user_keyboard(),
    )


@router.message(F.text == "🏆 Турниры")
async def tournaments_handler(message: Message):
    if await reject_if_not_admin_message(message):
        return
    await show_tournaments(message)


@router.callback_query(F.data == "adm:t:list")
async def tournaments_list_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_tournaments(callback)


@router.callback_query(F.data == "adm:t:create")
async def create_tournament_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if await reject_if_not_admin_callback(callback):
        return

    await callback.answer()
    await state.set_state(CreateTournament.name)
    await callback.message.answer(
        "➕ Создание турнира\n\nВведи название турнира:"
    )


@router.message(CreateTournament.name)
async def tournament_name_handler(message: Message, state: FSMContext):
    if await reject_if_not_admin_message(message):
        return

    name = (message.text or "").strip()
    if not name:
        await message.answer(
            "❌ Название не может быть пустым.\n\nВведи название турнира:"
        )
        return

    await state.update_data(name=name)
    await state.set_state(CreateTournament.season)
    await message.answer(
        "Отлично 👍\n\n"
        "Теперь введи сезон турнира.\n"
        "Например: 2026/27"
    )


@router.message(CreateTournament.season)
async def tournament_season_handler(message: Message, state: FSMContext):
    if await reject_if_not_admin_message(message):
        return

    season = (message.text or "").strip()
    if not season:
        await message.answer(
            "❌ Сезон не может быть пустым.\n\nНапример: 2026/27"
        )
        return

    data = await state.get_data()
    tournament_id = await db.create_tournament(
        name=data["name"],
        season=season,
        total_rounds=8,
    )
    await state.clear()
    await message.answer(
        "✅ Турнир создан!\n\n"
        f"🏆 {data['name']}\n"
        f"📅 Сезон: {season}\n"
        f"🔢 Туров: 8\n"
        f"🆔 ID турнира: {tournament_id}"
    )


async def show_tournament_menu(callback: CallbackQuery, tournament_id: int):
    tournament = await db.get_tournament(tournament_id)
    if tournament is None:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Telegram-группы",
                    callback_data=f"adm:g:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Туры",
                    callback_data=f"adm:rs:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📥 Результаты",
                    callback_data=f"adm:res:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Участники",
                    callback_data=f"adm:p:{tournament_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data=f"adm:st:{tournament_id}",
                )
            ],
            back_button("↩️ К турнирам", "adm:t:list"),
        ]
    )

    await send_or_edit(
        callback,
        "🏆 Турнир\n\n"
        f"Название: {tournament['name']}\n"
        f"Сезон: {tournament['season']}\n"
        f"Туров: {tournament['total_rounds']}\n"
        f"Статус: {tournament['status']}\n\n"
        "Выбери раздел:",
        keyboard,
    )


@router.callback_query(F.data.regexp(r"^adm:t:\d+$"))
async def tournament_menu_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_tournament_menu(callback, int(callback.data.split(":")[-1]))


# ---------------------------------------------------------------------------
# Rounds
# ---------------------------------------------------------------------------

async def show_rounds(callback: CallbackQuery, tournament_id: int):
    rounds = await db.get_rounds(tournament_id)
    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    f"📅 Тур {item['round_number']} "
                    f"({item['status']})"
                ),
                callback_data=f"adm:r:{item['id']}",
            )
        ]
        for item in rounds
    ]

    if not rounds:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="➕ Создать 8 туров",
                    callback_data=f"adm:rs:create:{tournament_id}",
                )
            ]
        )

    buttons.append(back_button("↩️ Назад", f"adm:t:{tournament_id}"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if rounds:
        text = f"📅 Туры турнира\n\nСоздано туров: {len(rounds)}\n\n"
        for item in rounds:
            text += f"Тур {item['round_number']} — {item['status']}\n"
    else:
        text = (
            "📅 Туры турнира\n\n"
            "Туры ещё не созданы.\n\n"
            "Нажми кнопку ниже, чтобы создать все 8 туров."
        )

    await send_or_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("adm:rs:create:"))
async def create_rounds_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return

    tournament_id = int(callback.data.split(":")[-1])
    existing = await db.get_rounds(tournament_id)
    if existing:
        await callback.answer("⚠️ Туры уже созданы", show_alert=True)
        return

    for round_number in range(1, 9):
        await db.create_round(tournament_id, round_number)

    await callback.answer("✅ 8 туров создано")
    await show_rounds(callback, tournament_id)


@router.callback_query(F.data.regexp(r"^adm:rs:\d+$"))
async def tournament_rounds_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_rounds(callback, int(callback.data.split(":")[-1]))


async def show_round_menu(callback: CallbackQuery, round_id: int):
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    complete = await db.round_results_complete(round_id)
    buttons = [
        [
            InlineKeyboardButton(
                text="📥 Загрузить 18 матчей",
                callback_data=f"adm:m:add18:{round_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🌐 Загрузить из API",
                callback_data=f"adm:m:api:{round_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ Добавить один матч",
                callback_data=f"adm:m:add1:{round_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Просмотреть матчи",
                callback_data=f"adm:m:list:{round_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="📥 Результаты матчей",
                callback_data=f"adm:res:r:{round_id}",
            )
        ],
    ]

    if complete:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="📊 Итоги тура",
                    callback_data=f"adm:rt:{round_id}",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text="📤 Отправить итоги тура",
                    callback_data=f"adm:rt:send:{round_id}",
                )
            ]
        )

    buttons.append(
        back_button("↩️ Назад", f"adm:rs:{round_item['tournament_id']}")
    )

    await send_or_edit(
        callback,
        "📅 Управление туром\n\n"
        f"Тур: {round_item['round_number']}\n"
        f"Статус: {round_item['status']}\n\n"
        "Выбери действие:",
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.regexp(r"^adm:r:\d+$"))
async def round_menu_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_round_menu(callback, int(callback.data.split(":")[-1]))


@router.callback_query(F.data.startswith("adm:m:api:"))
async def import_matches_from_api_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return

    if not FOOTBALL_DATA_API_TOKEN:
        await callback.answer(
            "Не задан FOOTBALL_DATA_API_TOKEN",
            show_alert=True,
        )
        return

    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    existing = await db.get_matches(round_id)
    if existing:
        await callback.answer(
            "В туре уже есть матчи. Импорт отменён.",
            show_alert=True,
        )
        return

    tournament = await db.get_tournament(round_item["tournament_id"])
    await callback.answer("Запрашиваю матчи...")
    try:
        matches = await get_champions_league_matchday(
            FOOTBALL_DATA_API_TOKEN,
            round_item["round_number"],
            tournament["season"] if tournament else None,
        )
    except FootballApiError as error:
        await callback.message.answer(f"❌ {error}")
        return

    if not matches:
        await callback.message.answer(
            "❌ API не вернул матчи для этого тура."
        )
        return

    try:
        for match in matches:
            await db.create_match(
                round_id=round_id,
                match_number=match["match_number"],
                home_team=match["home_team"],
                away_team=match["away_team"],
                kickoff_at=match["kickoff_at"],
            )
            await db.save_team_asset(
                match["home_team"],
                match.get("home_logo_url"),
                match.get("home_country_code"),
            )
            await db.save_team_asset(
                match["away_team"],
                match.get("away_logo_url"),
                match.get("away_country_code"),
            )
    except Exception:
        await callback.message.answer(
            "❌ Не удалось сохранить матчи из API. Импорт остановлен."
        )
        return

    await callback.message.answer(
        f"✅ Из API загружено матчей: {len(matches)}"
    )


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

async def show_matches(callback: CallbackQuery, round_id: int):
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    matches = await db.get_matches(round_id)
    if not matches:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[back_button("↩️ Назад", f"adm:r:{round_id}")]
        )
        await send_or_edit(
            callback,
            "⚽ Матчи\n\nВ этом туре матчей пока нет.",
            keyboard,
        )
        return

    text = f"⚽ Матчи — Тур {round_item['round_number']}\n\n"
    buttons = []
    for match in matches:
        local_time = format_kickoff_local(match["kickoff_at"])
        result = ""
        if match["result_home"] is not None:
            result = f" [{match['result_home']}:{match['result_away']}]"
        text += (
            f"{match['match_number']}. {format_match_teams(match['home_team'], match['away_team'])}\n"
            f"   {local_time}{result}\n"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"⚽ Матч №{match['match_number']}",
                    callback_data=f"adm:m:id:{match['id']}",
                )
            ]
        )

    buttons.append(back_button("↩️ Назад", f"adm:r:{round_id}"))
    await send_or_edit(
        callback,
        text,
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("adm:m:list:"))
async def view_matches_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_matches(callback, int(callback.data.split(":")[-1]))


async def show_match_card(
    callback: CallbackQuery,
    match_id: int,
    *,
    answer: bool = True,
):
    match = await db.get_match(match_id)
    if match is None:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return

    locked = db.match_locked_for_admin(match)
    buttons = []
    if not locked:
        buttons.extend(
            [
                [
                    InlineKeyboardButton(
                        text="✏️ Изменить",
                        callback_data=f"adm:m:edit:{match_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🗑 Удалить",
                        callback_data=f"adm:m:del:{match_id}",
                    )
                ],
            ]
        )
    else:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="📥 Результат",
                    callback_data=f"adm:res:m:{match_id}",
                )
            ]
        )

    buttons.append(back_button("↩️ К матчам", f"adm:m:list:{match['round_id']}"))

    note = ""
    if locked:
        note = (
            "\nМатч нельзя изменить или удалить: "
            "он уже начался или есть результат."
        )

    result_line = ""
    if match["result_home"] is not None:
        result_line = (
            f"Счёт: {match['result_home']}:{match['result_away']}\n"
        )

    await send_or_edit(
        callback,
        "⚽ Матч\n\n"
        f"Номер: {match['match_number']}\n"
        f"Дата: {format_kickoff_local(match['kickoff_at'])}\n"
        f"Хозяева: {match['home_team']}\n"
        f"Гости: {match['away_team']}\n"
        f"Статус: {match['status']}\n"
        f"{result_line}"
        f"{note}\n"
        "Выбери действие:",
        InlineKeyboardMarkup(inline_keyboard=buttons),
        answer=answer,
    )


@router.callback_query(F.data.startswith("adm:m:id:"))
async def admin_match_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_match_card(callback, int(callback.data.split(":")[-1]))


@router.callback_query(F.data.startswith("adm:m:edit:"))
async def edit_match_callback(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return

    match_id = int(callback.data.split(":")[-1])
    match = await db.get_match(match_id)
    if match is None:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return

    if db.match_locked_for_admin(match):
        await callback.answer(
            "Нельзя менять матч после начала или при наличии результата",
            show_alert=True,
        )
        return

    await state.set_state(EditMatch.data)
    await state.update_data(match_id=match_id, waiting_for="data")
    await callback.answer()
    await callback.message.answer(
        "✏️ Редактирование матча\n\n"
        f"Текущий матч:\n"
        f"№{match['match_number']} — "
        f"{match['home_team']} — {match['away_team']}\n\n"
        "Пришли новые данные одной строкой:\n\n"
        "номер|дата время|хозяева|гости\n\n"
        "Например:\n"
        "1|08.09.2026 21:00|АЕК Афины|ЛАСК"
    )


@router.message(EditMatch.data)
async def edit_match_input_handler(message: Message, state: FSMContext):
    if await reject_if_not_admin_message(message):
        return

    command = (message.text or "").strip().casefold()
    if command in {"/cancel", "отмена", "выход", "назад"}:
        await state.clear()
        await message.answer("❌ Редактирование матча отменено.")
        return

    try:
        parsed = parse_match_line(message.text or "")
    except ParseError as error:
        await message.answer(f"❌ {error}")
        return

    data = await state.get_data()
    match_id = data["match_id"]
    match = await db.get_match(match_id)
    if match is None:
        await state.clear()
        await message.answer("❌ Матч не найден.")
        return

    existing = await db.get_match_by_number(
        round_id=match["round_id"],
        match_number=parsed["match_number"],
        exclude_id=match_id,
    )
    if existing:
        await message.answer(
            f"❌ Матч №{parsed['match_number']} уже существует в этом туре.\n\n"
            "Выбери другой номер."
        )
        return

    await state.update_data(
        match_number=parsed["match_number"],
        home_team=parsed["home_team"],
        away_team=parsed["away_team"],
        kickoff_at=parsed["kickoff_utc"],
        date_time_text=parsed["date_time_text"],
        waiting_for="confirmation",
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Сохранить",
                    callback_data="adm:m:save_edit",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Отмена",
                    callback_data="adm:m:cancel_edit",
                )
            ],
        ]
    )

    await message.answer(
        "✏️ Проверь новые данные матча:\n\n"
        f"⚽ Матч №{parsed['match_number']}\n"
        f"🏠 {parsed['home_team']}\n"
        f"🚌 {parsed['away_team']}\n"
        f"🕐 {parsed['date_time_text']}\n\n"
        "Сохранить изменения?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "adm:m:save_edit", EditMatch.data)
async def save_edit_match_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if await reject_if_not_admin_callback(callback):
        return

    data = await state.get_data()
    match_id = data.get("match_id")
    if not match_id:
        await callback.answer("Нет данных для сохранения", show_alert=True)
        return

    match = await db.get_match(match_id)
    if match is None or db.match_locked_for_admin(match):
        await state.clear()
        await callback.answer("Матч нельзя изменить", show_alert=True)
        return

    await db.update_match(
        match_id=match_id,
        match_number=data["match_number"],
        home_team=data["home_team"],
        away_team=data["away_team"],
        kickoff_at=data["kickoff_at"],
    )
    await state.clear()
    await callback.answer("✅ Матч изменён")
    await show_match_card(callback, match_id, answer=False)


@router.callback_query(F.data == "adm:m:cancel_edit")
async def cancel_edit_match_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if await reject_if_not_admin_callback(callback):
        return

    data = await state.get_data()
    match_id = data.get("match_id")
    await state.clear()
    await callback.answer("Отменено")
    if match_id:
        await show_match_card(callback, match_id, answer=False)
    else:
        await callback.message.edit_text("❌ Изменение матча отменено.")


@router.callback_query(F.data.startswith("adm:m:del:"))
async def delete_match_confirm_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return

    match_id = int(callback.data.split(":")[-1])
    match = await db.get_match(match_id)
    if match is None:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return

    if db.match_locked_for_admin(match):
        await callback.answer(
            "Нельзя удалить матч после начала или при наличии результата",
            show_alert=True,
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Да, удалить",
                    callback_data=f"adm:m:delok:{match_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Отмена",
                    callback_data=f"adm:m:id:{match_id}",
                )
            ],
        ]
    )
    await send_or_edit(
        callback,
        "⚠️ Удаление матча\n\n"
        "Ты действительно хочешь удалить этот матч?\n\n"
        "Это действие нельзя будет отменить.",
        keyboard,
    )


@router.callback_query(F.data.startswith("adm:m:delok:"))
async def confirm_delete_match_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return

    match_id = int(callback.data.split(":")[-1])
    match = await db.get_match(match_id)
    if match is None:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return

    if db.match_locked_for_admin(match):
        await callback.answer("Матч нельзя удалить", show_alert=True)
        return

    round_id = match["round_id"]
    await db.delete_match(match_id)
    await callback.answer("✅ Матч удалён")
    await show_matches(callback, round_id)


@router.callback_query(F.data.startswith("adm:m:add1:"))
async def add_single_match_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if await reject_if_not_admin_callback(callback):
        return

    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    await state.set_state(AddSingleMatch.data)
    await state.update_data(round_id=round_id)
    await callback.answer()
    await callback.message.answer(
        "➕ Добавление одного матча\n\n"
        "Пришли данные одной строкой:\n\n"
        "номер|дата время|хозяева|гости\n\n"
        "Например:\n"
        "18|10.09.2026 23:00|Манчестер Юнайтед|Сабах"
    )


@router.message(AddSingleMatch.data)
async def add_single_match_input_handler(
    message: Message,
    state: FSMContext,
):
    if await reject_if_not_admin_message(message):
        return

    try:
        parsed = parse_match_line(message.text or "")
    except ParseError as error:
        await message.answer(f"❌ {error}")
        return

    data = await state.get_data()
    round_id = data["round_id"]
    existing = await db.get_match_by_number(
        round_id,
        parsed["match_number"],
    )
    if existing:
        await message.answer(
            f"❌ Матч №{parsed['match_number']} уже существует в этом туре."
        )
        return

    await db.create_match(
        round_id=round_id,
        match_number=parsed["match_number"],
        home_team=parsed["home_team"],
        away_team=parsed["away_team"],
        kickoff_at=parsed["kickoff_utc"],
    )
    await state.clear()
    await message.answer(
        "✅ Матч добавлен!\n\n"
        f"⚽ Матч №{parsed['match_number']}\n"
        f"🏠 {parsed['home_team']}\n"
        f"🚌 {parsed['away_team']}\n"
        f"🕐 {parsed['date_time_text']}"
    )


@router.callback_query(F.data.startswith("adm:m:add18:"))
async def add_matches_callback(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return

    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    existing = await db.get_matches(round_id)
    if existing:
        await callback.answer(
            "В туре уже есть матчи. Удали их или добавляй по одному.",
            show_alert=True,
        )
        return

    await callback.answer()
    await state.set_state(AddMatches.matches)
    await state.update_data(round_id=round_id)
    await callback.message.answer(
        "⚽ Добавление матчей\n\n"
        "Пришли все 18 матчей одним сообщением.\n\n"
        "Формат каждой строки:\n"
        "номер|дата время|хозяева|гости\n\n"
        "Например:\n"
        "1|15.09.2026 19:45|Атлетик|Арсенал\n"
        "2|15.09.2026 22:00|Манчестер Сити|Наполи\n\n"
        "Всего должно быть 18 строк."
    )


@router.message(AddMatches.matches)
async def matches_input_handler(message: Message, state: FSMContext):
    if await reject_if_not_admin_message(message):
        return

    if not message.text:
        await message.answer("❌ Нужно отправить список матчей текстом.")
        return

    lines = [
        line.strip()
        for line in message.text.splitlines()
        if line.strip()
    ]
    if len(lines) != 18:
        await message.answer(
            f"❌ Найдено строк: {len(lines)}.\n\n"
            "Должно быть ровно 18 матчей."
        )
        return

    matches = []
    numbers = set()

    for line_number, line in enumerate(lines, start=1):
        try:
            parsed = parse_match_line(line)
        except ParseError as error:
            await message.answer(
                f"❌ Ошибка в строке {line_number}:\n{line}\n\n{error}"
            )
            return

        if parsed["match_number"] in numbers:
            await message.answer(
                f"❌ Номер матча {parsed['match_number']} встречается несколько раз."
            )
            return

        numbers.add(parsed["match_number"])
        matches.append(parsed)

    if numbers != set(range(1, 19)):
        await message.answer(
            "❌ Номера матчей должны быть от 1 до 18 без пропусков."
        )
        return

    await state.update_data(matches=matches)

    preview = "📋 Проверь список матчей:\n\n"
    for match in matches:
        preview += (
            f"{match['match_number']}. {match['date_time_text']} — "
            f"{match['home_team']} — {match['away_team']}\n"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Сохранить",
                    callback_data="adm:m:save18",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Отмена",
                    callback_data="adm:m:cancel18",
                )
            ],
        ]
    )
    await message.answer(preview, reply_markup=keyboard)


@router.callback_query(F.data == "adm:m:save18", AddMatches.matches)
async def save_matches_callback(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return

    data = await state.get_data()
    matches = data.get("matches")
    round_id = data.get("round_id")
    if not matches or not round_id:
        await callback.answer("Нет данных для сохранения", show_alert=True)
        return

    try:
        for match in matches:
            await db.create_match(
                round_id=round_id,
                match_number=match["match_number"],
                home_team=match["home_team"],
                away_team=match["away_team"],
                kickoff_at=match["kickoff_utc"],
            )
    except Exception:
        await callback.answer()
        await callback.message.answer(
            "❌ Не удалось сохранить матчи. Возможно, номера уже заняты."
        )
        return

    await state.clear()
    await callback.answer("✅ Матчи сохранены")
    await callback.message.edit_text(
        f"✅ Матчи успешно сохранены!\n\nДобавлено матчей: {len(matches)}"
    )

    round_item = await db.get_round(round_id)
    if round_item:
        notice = format_round_fixtures(round_item, matches)
        groups_sent, users_sent = await broadcast_chunks(
            callback.bot,
            round_item["tournament_id"],
            notice,
        )
        await callback.message.answer(
            "📤 Расписание тура отправлено участникам и в группы.\n"
            f"Групп: {groups_sent}\n"
            f"Участников: {users_sent}"
        )


@router.callback_query(F.data == "adm:m:cancel18")
async def cancel_matches_callback(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.edit_text("❌ Добавление матчей отменено.")


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

async def show_groups(callback: CallbackQuery, tournament_id: int):
    groups = await db.get_groups(tournament_id)
    active = [group for group in groups if group["is_active"]]
    text = "📱 Telegram-группы турнира\n\n"
    if not active:
        text += "Активных групп нет.\n\n"
        text += (
            "Чтобы привязать группу:\n"
            "1) Добавь бота в группу\n"
            f"2) Напиши в группе /bind {tournament_id}\n"
            "или нажми «Привязать» и пришли chat_id."
        )
    else:
        for group in active:
            text += (
                f"• {group['title']}\n"
                f"  chat_id: {group['telegram_chat_id']}\n"
            )

    buttons = [
        [
            InlineKeyboardButton(
                text="➕ Привязать по chat_id",
                callback_data=f"adm:g:bind:{tournament_id}",
            )
        ]
    ]
    for group in active:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🔓 Отвязать {group['title'][:20]}",
                    callback_data=f"adm:g:off:{group['id']}:{tournament_id}",
                )
            ]
        )
    buttons.append(back_button("↩️ Назад", f"adm:t:{tournament_id}"))
    await send_or_edit(
        callback,
        text,
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("adm:g:bind:"))
async def bind_group_start(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return

    tournament_id = int(callback.data.split(":")[-1])
    await state.set_state(BindGroup.chat_id)
    await state.update_data(tournament_id=tournament_id)
    await callback.answer()
    await callback.message.answer(
        "Пришли chat_id группы (обычно отрицательное число).\n\n"
        f"Или в самой группе напиши: /bind {tournament_id}"
    )


@router.message(BindGroup.chat_id)
async def bind_group_chat_id_handler(message: Message, state: FSMContext):
    if await reject_if_not_admin_message(message):
        return

    text = (message.text or "").strip()
    try:
        chat_id = int(text)
    except ValueError:
        await message.answer("❌ chat_id должен быть числом.")
        return

    data = await state.get_data()
    tournament_id = data["tournament_id"]
    existing = await db.get_group_by_chat_id(chat_id)
    title = existing["title"] if existing else f"Группа {chat_id}"

    if (
        existing
        and existing["is_active"]
        and existing["tournament_id"] != tournament_id
    ):
        await state.update_data(
            chat_id=chat_id,
            title=title,
            rebind=True,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Перепривязать",
                        callback_data="adm:g:rebind_ok",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="↩️ Отмена",
                        callback_data="adm:g:rebind_no",
                    )
                ],
            ]
        )
        await message.answer(
            "Эта группа уже привязана к другому турниру.\n"
            "Перепривязать?",
            reply_markup=keyboard,
        )
        return

    await db.bind_group(chat_id, title, tournament_id)
    await state.clear()
    await message.answer(
        f"✅ Группа привязана к турниру {tournament_id}.\n"
        f"chat_id: {chat_id}"
    )


@router.callback_query(F.data == "adm:g:rebind_ok", BindGroup.chat_id)
async def rebind_ok(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return
    data = await state.get_data()
    await db.bind_group(
        data["chat_id"],
        data.get("title") or f"Группа {data['chat_id']}",
        data["tournament_id"],
    )
    tournament_id = data["tournament_id"]
    await state.clear()
    await callback.answer("Готово")
    await show_groups(callback, tournament_id)


@router.callback_query(F.data == "adm:g:rebind_no")
async def rebind_no(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return
    data = await state.get_data()
    tournament_id = data.get("tournament_id")
    await state.clear()
    await callback.answer("Отменено")
    if tournament_id:
        await show_groups(callback, tournament_id)


@router.callback_query(F.data.startswith("adm:g:off:"))
async def unbind_group_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    _, _, _, group_id, tournament_id = callback.data.split(":")
    await db.unbind_group(int(group_id))
    await callback.answer("Группа отвязана")
    await show_groups(callback, int(tournament_id))


@router.callback_query(F.data.regexp(r"^adm:g:\d+$"))
async def groups_menu_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_groups(callback, int(callback.data.split(":")[-1]))


@router.message(Command("bind"))
async def bind_command(message: Message, command: CommandObject):
    if await reject_if_not_admin_message(message):
        await message.answer("⛔ Только администратор может привязывать группы.")
        return

    if message.chat.type not in {"group", "supergroup"}:
        await message.answer(
            "Команду /bind нужно отправить в Telegram-группе, "
            "куда добавлен бот.\n"
            "Формат: /bind ID_турнира"
        )
        return

    tournament_id = None
    if command.args:
        try:
            tournament_id = int(command.args.strip())
        except ValueError:
            await message.answer("❌ ID турнира должен быть числом.")
            return
    else:
        tournaments = await db.get_joinable_tournaments()
        if len(tournaments) == 1:
            tournament_id = tournaments[0]["id"]
        else:
            await message.answer(
                "Укажи турнир: /bind ID\n\n"
                "Доступные турниры можно посмотреть в админке."
            )
            return

    tournament = await db.get_tournament(tournament_id)
    if tournament is None:
        await message.answer("❌ Турнир не найден.")
        return

    existing = await db.get_group_by_chat_id(message.chat.id)
    if (
        existing
        and existing["is_active"]
        and existing["tournament_id"] != tournament_id
    ):
        await db.bind_group(
            message.chat.id,
            message.chat.title or f"Группа {message.chat.id}",
            tournament_id,
        )
        await message.answer(
            f"⚠️ Группа перепривязана к турниру «{tournament['name']}»."
        )
        return

    await db.bind_group(
        message.chat.id,
        message.chat.title or f"Группа {message.chat.id}",
        tournament_id,
    )
    await message.answer(
        f"✅ Группа привязана к турниру «{tournament['name']}» "
        f"({tournament['season']})."
    )


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------

async def show_participants(callback: CallbackQuery, tournament_id: int):
    participants = await db.get_participants(tournament_id)
    text = "👥 Участники турнира\n\n"
    if not participants:
        text += "Пока никого нет. Игроки попадают сюда после /start."
        buttons = [back_button("↩️ Назад", f"adm:t:{tournament_id}")]
        await send_or_edit(
            callback,
            text,
            InlineKeyboardMarkup(inline_keyboard=buttons),
        )
        return

    buttons = []
    for participant in participants:
        status = "активен" if participant["is_active"] else "неактивен"
        text += (
            f"• {display_name(participant)}\n"
            f"  {status}, с {participant['joined_at'][:10]}\n"
        )
        action = "Деактивировать" if participant["is_active"] else "Активировать"
        new_value = 0 if participant["is_active"] else 1
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{action}: {display_name(participant)[:20]}",
                    callback_data=(
                        f"adm:p:set:{participant['id']}:{new_value}:{tournament_id}"
                    ),
                )
            ]
        )

    buttons.append(back_button("↩️ Назад", f"adm:t:{tournament_id}"))
    await send_or_edit(
        callback,
        text,
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("adm:p:set:"))
async def set_participant_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    _, _, _, participant_id, is_active, tournament_id = callback.data.split(":")
    await db.set_participant_active(int(participant_id), int(is_active))
    await callback.answer("Сохранено")
    await show_participants(callback, int(tournament_id))


@router.callback_query(F.data.regexp(r"^adm:p:\d+$"))
async def participants_menu_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_participants(callback, int(callback.data.split(":")[-1]))


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

async def show_results_rounds(callback: CallbackQuery, tournament_id: int):
    rounds = await db.get_rounds(tournament_id)
    if not rounds:
        await send_or_edit(
            callback,
            "Сначала создай туры.",
            InlineKeyboardMarkup(
                inline_keyboard=[
                    back_button("↩️ Назад", f"adm:t:{tournament_id}")
                ]
            ),
        )
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=f"Тур {item['round_number']} ({item['status']})",
                callback_data=f"adm:res:r:{item['id']}",
            )
        ]
        for item in rounds
    ]
    buttons.append(back_button("↩️ Назад", f"adm:t:{tournament_id}"))
    await send_or_edit(
        callback,
        "📥 Выбери тур для ввода результатов:",
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("adm:res:r:"))
async def results_round_matches(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return

    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    matches = await db.get_matches(round_id)
    if not matches:
        await send_or_edit(
            callback,
            "В туре нет матчей.",
            InlineKeyboardMarkup(
                inline_keyboard=[back_button("↩️ Назад", f"adm:r:{round_id}")]
            ),
        )
        return

    text = f"📥 Результаты — Тур {round_item['round_number']}\n\n"
    buttons = []
    for match in matches:
        if match["result_home"] is not None:
            score = f"{match['result_home']}:{match['result_away']}"
        else:
            score = "—"
        text += (
            f"{match['match_number']}. {match['home_team']} — "
            f"{match['away_team']}: {score}\n"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"№{match['match_number']} ({score})",
                    callback_data=f"adm:res:m:{match['id']}",
                )
            ]
        )

    buttons.append(back_button("↩️ Назад", f"adm:r:{round_id}"))
    await send_or_edit(
        callback,
        text,
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("adm:res:m:"))
async def enter_result_callback(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return

    match_id = int(callback.data.split(":")[-1])
    match = await db.get_match(match_id)
    if match is None:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return

    if not match_has_started(match["kickoff_at"]):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Всё равно ввести",
                        callback_data=f"adm:res:force:{match_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="↩️ Назад",
                        callback_data=f"adm:res:r:{match['round_id']}",
                    )
                ],
            ]
        )
        await send_or_edit(
            callback,
            "Матч ещё не начался по расписанию.\n"
            "Ввести результат всё равно?",
            keyboard,
        )
        return

    await start_result_input(callback, state, match)


@router.callback_query(F.data.startswith("adm:res:force:"))
async def force_result_callback(callback: CallbackQuery, state: FSMContext):
    if await reject_if_not_admin_callback(callback):
        return
    match = await db.get_match(int(callback.data.split(":")[-1]))
    if match is None:
        await callback.answer("❌ Матч не найден", show_alert=True)
        return
    await start_result_input(callback, state, match)


async def start_result_input(callback: CallbackQuery, state: FSMContext, match):
    await state.set_state(EnterResult.score)
    await state.update_data(match_id=match["id"])
    await callback.answer()
    current = ""
    if match["result_home"] is not None:
        current = (
            f"\nСейчас: {match['result_home']}:{match['result_away']}\n"
            "Новый счёт перезапишет результат и пересчитает очки."
        )
    await callback.message.answer(
        "Введи счёт матча в формате 2:1\n\n"
        f"{match['home_team']} — {match['away_team']}"
        f"{current}"
    )


@router.message(EnterResult.score)
async def enter_result_score_handler(message: Message, state: FSMContext):
    if await reject_if_not_admin_message(message):
        return

    try:
        home_score, away_score = parse_score(message.text or "")
    except ParseError as error:
        await message.answer(f"❌ {error}")
        return

    data = await state.get_data()
    match_id = data["match_id"]
    match = await db.get_match(match_id)
    if match is None:
        await state.clear()
        await message.answer("❌ Матч не найден.")
        return

    await db.set_match_result(match_id, home_score, away_score)
    await state.clear()
    await message.answer(
        "✅ Результат сохранён, очки пересчитаны.\n\n"
        f"{match['home_team']} {home_score}:{away_score} {match['away_team']}"
    )


@router.callback_query(F.data.regexp(r"^adm:res:\d+$"))
async def results_tournament_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await show_results_rounds(callback, int(callback.data.split(":")[-1]))


# ---------------------------------------------------------------------------
# Round table / send
# ---------------------------------------------------------------------------

def round_table_text(round_item, standings) -> str:
    return format_standings(
        f"📊 Результаты тура {round_item['round_number']}",
        standings,
    )


@router.callback_query(F.data.startswith("adm:rt:send:"))
async def send_round_table_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return

    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    if not await db.round_results_complete(round_id):
        await callback.answer(
            "Сначала введи результаты всех матчей тура",
            show_alert=True,
        )
        return

    await db.set_round_status(round_id, "finished")
    standings = await db.get_round_standings(round_id)
    text = round_table_text(round_item, standings)
    groups_sent, users_sent = await broadcast_chunks(
        callback.bot,
        round_item["tournament_id"],
        text,
    )

    await callback.answer("Итоги отправлены")
    await callback.message.answer(
        f"📤 Итоги тура отправлены.\n"
        f"Групп: {groups_sent}\n"
        f"Участников: {users_sent}"
    )


@router.callback_query(F.data.regexp(r"^adm:rt:\d+$"))
async def show_round_table_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return

    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if round_item is None:
        await callback.answer("❌ Тур не найден", show_alert=True)
        return

    standings = await db.get_round_standings(round_id)
    text = round_table_text(round_item, standings)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Отправить итоги",
                    callback_data=f"adm:rt:send:{round_id}",
                )
            ],
            back_button("↩️ Назад", f"adm:r:{round_id}"),
        ]
    )

    await callback.answer()
    for chunk in chunk_text(text):
        await callback.message.answer(chunk)
    await callback.message.answer("Действия:", reply_markup=keyboard)


def format_round_fixtures(round_item, matches) -> str:
    lines = [
        f"📝 Открыт приём прогнозов — Тур {round_item['round_number']}",
        "",
        "Прогнозы принимаются в личке с ботом до начала каждого матча.",
        "",
    ]
    for match in matches:
        kickoff = match.get("date_time_text")
        if not kickoff:
            kickoff = format_kickoff_local(
                match.get("kickoff_utc") or match["kickoff_at"]
            )
        lines.append(
            f"{match['match_number']}. {kickoff} — "
            f"{match['home_team']} — {match['away_team']}"
        )
    return "\n".join(lines)


async def send_admin_standings(target: Message | CallbackQuery, tournament_id: int):
    tournament = await db.get_tournament(tournament_id)
    if tournament is None:
        if isinstance(target, CallbackQuery):
            await target.answer("❌ Турнир не найден", show_alert=True)
        else:
            await target.answer("❌ Турнир не найден.")
        return

    standings = await db.get_tournament_standings(tournament_id)
    text = format_standings(
        f"📊 Статистика — {tournament['name']} ({tournament['season']})",
        standings,
    )
    chunks = chunk_text(text)
    if isinstance(target, CallbackQuery):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[back_button("↩️ Назад", f"adm:t:{tournament_id}")]
        )
        await send_or_edit(target, chunks[0], keyboard if len(chunks) == 1 else None)
        for chunk in chunks[1:]:
            await target.message.answer(chunk)
    else:
        for chunk in chunks:
            await target.answer(chunk)


@router.message(F.text == "📊 Статистика")
async def admin_stats_handler(message: Message):
    tournaments = await db.get_tournaments()
    if not tournaments:
        await message.answer("Сначала создай турнир.")
        return
    if len(tournaments) == 1:
        await send_admin_standings(message, tournaments[0]["id"])
        return
    await message.answer(
        "Выбери турнир для статистики:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{item['name']} ({item['season']})",
                        callback_data=f"adm:st:{item['id']}",
                    )
                ]
                for item in tournaments
            ]
        ),
    )


@router.message(F.text == "📥 Результаты")
async def admin_results_handler(message: Message):
    tournaments = await db.get_tournaments()
    if not tournaments:
        await message.answer("Сначала создай турнир.")
        return
    if len(tournaments) == 1:
        rounds = await db.get_rounds(tournaments[0]["id"])
        if not rounds:
            await message.answer("Сначала создай туры.")
            return
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"Тур {item['round_number']} ({item['status']})",
                    callback_data=f"adm:res:r:{item['id']}",
                )
            ]
            for item in rounds
        ]
        await message.answer(
            "📥 Выбери тур для ввода результатов:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
        return

    await message.answer(
        "Выбери турнир:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{item['name']} ({item['season']})",
                        callback_data=f"adm:res:{item['id']}",
                    )
                ]
                for item in tournaments
            ]
        ),
    )


@router.callback_query(F.data.regexp(r"^adm:st:\d+$"))
async def admin_stats_callback(callback: CallbackQuery):
    if await reject_if_not_admin_callback(callback):
        return
    await send_admin_standings(callback, int(callback.data.split(":")[-1]))
