from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from access import format_standings, is_admin
from database import db
from keyboards import user_keyboard
from states import EnterPrediction
from texts.rules import RULES_TEXT
from utils import (
    ParseError,
    chunk_text,
    format_match_teams,
    format_kickoff_compact,
    format_kickoff_local,
    match_has_started,
    parse_score,
)


router = Router()
router.message.filter(F.chat.type == "private")

PREDICTION_PAGE_SIZE = 6

ROUND_STATUS_LABELS = {
    "open": "открыт",
    "upcoming": "ожидается",
}


def round_status_label(status: str) -> str:
    return ROUND_STATUS_LABELS.get(status, status)


def back_button(text: str, callback_data: str):
    return [InlineKeyboardButton(text=text, callback_data=callback_data)]


async def send_or_edit(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
):
    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)


async def ensure_user_and_join(message: Message):
    user = message.from_user
    db_user = await db.create_or_update_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    await db.join_user_to_open_tournaments(db_user["id"])
    return db_user


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.")


@router.message(Command("admin"))
async def admin_forbidden_handler(message: Message):
    await message.answer("⛔ У тебя нет доступа к панели администратора.")


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    db_user = await ensure_user_and_join(message)

    extra = ""
    if is_admin(message.from_user.id):
        extra = "\n\nКоманда /admin открывает панель администратора."

    await message.answer(
        "🏆 Привет!\n\n"
        "Это бот прогнозов Лиги чемпионов.\n"
        "Делай прогнозы в личке до начала матча, "
        "смотри таблицу и архив туров.\n\n"
        f"Ты зарегистрирован под ID {db_user['id']}."
        f"{extra}",
        reply_markup=user_keyboard(),
    )


@router.message(Command("rules"))
@router.message(F.text == "ℹ️ Правила")
async def rules_handler(message: Message):
    await ensure_user_and_join(message)
    await message.answer(RULES_TEXT)


async def pick_tournament_keyboard(
    tournaments,
    prefix: str,
):
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{item['name']} ({item['season']})",
                callback_data=f"{prefix}:{item['id']}",
            )
        ]
        for item in tournaments
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def user_tournaments_or_hint(message: Message, db_user):
    tournaments = await db.get_user_tournaments(db_user["id"])
    if not tournaments:
        joinable = await db.get_joinable_tournaments()
        if joinable:
            await db.join_user_to_open_tournaments(db_user["id"])
            tournaments = await db.get_user_tournaments(db_user["id"])
    return tournaments


async def prediction_round_buttons(tournament_id: int, rounds, user_id: int):
    db_user = await db.get_user(user_id)
    participant = await db.get_participant(tournament_id, db_user["id"])
    buttons = []
    for item in rounds:
        predicted, total = await db.predicted_count_for_round(
            participant["id"],
            item["id"],
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"Тур {item['round_number']} · {predicted}/{total}",
                    callback_data=f"u:pr:r:{item['id']}",
                )
            ]
        )
    return buttons


@router.message(F.text == "📝 Сделать прогноз")
async def make_prediction_handler(message: Message, state: FSMContext):
    await state.clear()
    db_user = await ensure_user_and_join(message)
    tournaments = await user_tournaments_or_hint(message, db_user)
    if not tournaments:
        await message.answer("Сейчас нет открытых турниров для прогнозов.")
        return

    if len(tournaments) == 1:
        await show_prediction_rounds_message(message, tournaments[0]["id"])
        return

    await message.answer(
        "Выбери турнир:",
        reply_markup=await pick_tournament_keyboard(tournaments, "u:pr:t"),
    )


async def show_prediction_rounds_message(message: Message, tournament_id: int):
    rounds = await db.get_rounds_with_open_matches(tournament_id)
    if not rounds:
        await message.answer("Нет открытых матчей для прогнозов.")
        return

    buttons = await prediction_round_buttons(
        tournament_id,
        rounds,
        message.from_user.id,
    )
    await message.answer(
        "Выбери тур:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("u:pr:t:"))
async def prediction_tournament_callback(callback: CallbackQuery):
    tournament_id = int(callback.data.split(":")[-1])
    rounds = await db.get_rounds_with_open_matches(tournament_id)
    if not rounds:
        await send_or_edit(callback, "Нет открытых матчей для прогнозов.")
        return

    buttons = await prediction_round_buttons(
        tournament_id,
        rounds,
        callback.from_user.id,
    )
    await send_or_edit(
        callback,
        "Выбери тур:",
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("u:pr:r:"))
async def prediction_round_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()
    round_id = int(callback.data.split(":")[-1])
    await show_prediction_page(callback, round_id, 0)


@router.callback_query(F.data.startswith("u:pr:p:"))
async def prediction_page_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()
    _, _, _, round_id, page = callback.data.split(":")
    await show_prediction_page(callback, int(round_id), int(page))


async def show_prediction_page(
    callback: CallbackQuery,
    round_id: int,
    page: int,
):
    await db.lock_started_matches(round_id)

    round_item = await db.get_round(round_id)
    db_user = await db.get_user(callback.from_user.id)
    if db_user is None or round_item is None:
        await callback.answer("Сначала нажми /start", show_alert=True)
        return

    participant = await db.get_participant(
        round_item["tournament_id"],
        db_user["id"],
    )
    if participant is None or not participant["is_active"]:
        await callback.answer(
            "Ты не активный участник этого турнира",
            show_alert=True,
        )
        return

    matches = await db.get_matches(round_id)
    predictions = await db.get_user_predictions_for_round(
        participant["id"],
        round_id,
    )
    predictions_by_match = {
        row["id"]: row for row in predictions if row["pred_home"] is not None
    }

    page_count = max(
        1,
        (len(matches) + PREDICTION_PAGE_SIZE - 1) // PREDICTION_PAGE_SIZE,
    )
    page = max(0, min(page, page_count - 1))
    page_matches = matches[
        page * PREDICTION_PAGE_SIZE:(page + 1) * PREDICTION_PAGE_SIZE
    ]
    text = (
        f"📝 Прогнозы — Тур {round_item['round_number']}\n"
        f"Матчи {page * PREDICTION_PAGE_SIZE + 1}-"
        f"{page * PREDICTION_PAGE_SIZE + len(page_matches)} "
        f"из {len(matches)}\n\n"
    )
    buttons = []

    for match in page_matches:
        prediction = predictions_by_match.get(match["id"])
        started = match_has_started(match["kickoff_at"]) or match["status"] != "scheduled"
        if prediction:
            mark = f"{prediction['pred_home']}:{prediction['pred_away']}"
        else:
            mark = "—"

        prediction_status = (
            "✅"
            if prediction
            else "❌"
        )
        status = f"🔒 · {prediction_status}" if started else prediction_status
        text += (
            f"{match['match_number']}. "
            f"{format_match_teams(match['home_team'], match['away_team'], match['home_display_name'], match['away_display_name'], match['home_country_code'], match['away_country_code'], match['home_flag_emoji'], match['away_flag_emoji'])}\n"
            f"   {format_kickoff_compact(match['kickoff_at'])} · {status}\n"
            f"   Прогноз: {mark if prediction else 'не задан'}\n\n"
        )
        if not started:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=(
                            f"✏️ Изменить прогноз №{match['match_number']}"
                            if prediction
                            else f"➕ Добавить прогноз №{match['match_number']}"
                        ),
                        callback_data=f"u:pr:m:{match['id']}",
                    )
                ]
            )

    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущие",
                callback_data=f"u:pr:p:{round_id}:{page - 1}",
            )
        )
    if page < page_count - 1:
        navigation.append(
            InlineKeyboardButton(
                text="Следующие ➡️",
                callback_data=f"u:pr:p:{round_id}:{page + 1}",
            )
        )
    if navigation:
        buttons.append(navigation)
    buttons.append(
        back_button("↩️ К турам", f"u:pr:t:{round_item['tournament_id']}"),
    )
    await send_or_edit(
        callback,
        text.rstrip(),
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("u:pr:m:"))
async def prediction_match_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    match_id = int(callback.data.split(":")[-1])
    await db.lock_started_matches()

    match = await db.get_match(match_id)
    if match is None:
        await callback.answer("Матч не найден", show_alert=True)
        return

    if match_has_started(match["kickoff_at"]) or match["status"] != "scheduled":
        db_user = await db.get_user(callback.from_user.id)
        if db_user:
            participant = await db.get_participant(
                match["tournament_id"],
                db_user["id"],
            )
            if participant:
                prediction = await db.get_prediction(participant["id"], match_id)
                if prediction:
                    await db.lock_prediction(prediction["id"])
        await callback.answer(
            "Приём прогнозов на этот матч закрыт",
            show_alert=True,
        )
        return

    await show_prediction_form(callback, state, match)


async def show_prediction_form(
    callback: CallbackQuery,
    state: FSMContext,
    match,
):
    await state.set_state(EnterPrediction.score)
    await state.update_data(match_id=match["id"])
    await callback.answer()
    current = ""
    db_user = await db.get_user(callback.from_user.id)
    if db_user:
        participant = await db.get_participant(
            match["tournament_id"],
            db_user["id"],
        )
        if participant:
            prediction = await db.get_prediction(participant["id"], match["id"])
            if prediction:
                current = (
                    f"\nТекущий прогноз: "
                    f"{prediction['home_score']}:{prediction['away_score']}"
                )

    buttons = [
        back_button("↩️ К матчам", f"u:pr:r:{match['round_id']}"),
    ]

    await callback.message.edit_text(
        "Введи счёт в формате 2:1\n\n"
        f"{format_match_teams(match['home_team'], match['away_team'], match['home_display_name'], match['away_display_name'], match['home_country_code'], match['away_country_code'], match['home_flag_emoji'], match['away_flag_emoji'])}\n"
        f"Начало: {format_kickoff_local(match['kickoff_at'])}"
        f"{current}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.message(EnterPrediction.score)
async def prediction_score_handler(message: Message, state: FSMContext):
    db_user = await ensure_user_and_join(message)

    try:
        home_score, away_score = parse_score(message.text or "")
    except ParseError as error:
        await message.answer(f"❌ {error}")
        return

    data = await state.get_data()
    match_id = data["match_id"]
    await db.lock_started_matches()
    match = await db.get_match(match_id)
    if match is None:
        await state.clear()
        await message.answer("Матч не найден.")
        return

    if match_has_started(match["kickoff_at"]) or match["status"] != "scheduled":
        participant = await db.get_participant(
            match["tournament_id"],
            db_user["id"],
        )
        if participant:
            prediction = await db.get_prediction(participant["id"], match_id)
            if prediction:
                await db.lock_prediction(prediction["id"])
        await state.clear()
        await message.answer("Приём прогнозов на этот матч уже закрыт.")
        return

    participant = await db.get_participant(
        match["tournament_id"],
        db_user["id"],
    )
    if participant is None:
        await db.ensure_participant(match["tournament_id"], db_user["id"])
        participant = await db.get_participant(
            match["tournament_id"],
            db_user["id"],
        )

    if not participant["is_active"]:
        await state.clear()
        await message.answer("Ты деактивирован в этом турнире и не можешь делать прогнозы.")
        return

    saved = await db.upsert_prediction(
        participant["id"],
        match_id,
        home_score,
        away_score,
    )
    await state.clear()
    if not saved:
        await message.answer("Приём прогнозов на этот матч уже закрыт.")
        return

    await message.answer(
        "✅ Прогноз сохранён.\n\n"
        f"{format_match_teams(match['home_team'], match['away_team'], match['home_display_name'], match['away_display_name'], match['home_country_code'], match['away_country_code'], match['home_flag_emoji'], match['away_flag_emoji'])}\n"
        f"Счёт: {home_score}:{away_score}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➡️ Другой матч этого тура",
                        callback_data=f"u:pr:r:{match['round_id']}",
                    )
                ]
            ]
        ),
    )


@router.message(F.text == "📋 Мои прогнозы")
async def my_predictions_handler(message: Message):
    db_user = await ensure_user_and_join(message)
    tournaments = await user_tournaments_or_hint(message, db_user)
    if not tournaments:
        await message.answer("Нет турниров, в которых ты участвуешь.")
        return

    if len(tournaments) == 1:
        await show_my_rounds(message, tournaments[0]["id"], db_user["id"])
        return

    await message.answer(
        "Выбери турнир:",
        reply_markup=await pick_tournament_keyboard(tournaments, "u:my:t"),
    )


async def show_my_rounds(message: Message, tournament_id: int, user_id: int):
    rounds = await db.get_rounds(tournament_id)
    if not rounds:
        await message.answer("Туры ещё не созданы.")
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    f"Тур {item['round_number']} "
                    f"({round_status_label(item['status'])})"
                ),
                callback_data=f"u:my:r:{item['id']}",
            )
        ]
        for item in rounds
    ]
    await message.answer(
        "Выбери тур:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("u:my:t:"))
async def my_predictions_tournament(callback: CallbackQuery):
    db_user = await db.get_user(callback.from_user.id)
    if db_user is None:
        await callback.answer("Сначала /start", show_alert=True)
        return

    tournament_id = int(callback.data.split(":")[-1])
    rounds = await db.get_rounds(tournament_id)
    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    f"Тур {item['round_number']} "
                    f"({round_status_label(item['status'])})"
                ),
                callback_data=f"u:my:r:{item['id']}",
            )
        ]
        for item in rounds
    ]
    await send_or_edit(
        callback,
        "Выбери тур:",
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("u:my:r:"))
async def my_predictions_round(callback: CallbackQuery):
    db_user = await db.get_user(callback.from_user.id)
    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if db_user is None or round_item is None:
        await callback.answer("Данные не найдены", show_alert=True)
        return

    participant = await db.get_participant(
        round_item["tournament_id"],
        db_user["id"],
    )
    if participant is None:
        await callback.answer("Ты не участник турнира", show_alert=True)
        return

    rows = await db.get_user_predictions_for_round(
        participant["id"],
        round_id,
    )
    predicted, total = await db.predicted_count_for_round(
        participant["id"],
        round_id,
    )
    text = (
        f"📋 Мои прогнозы — Тур {round_item['round_number']}\n"
        f"Заполнено: {predicted} из {total}\n\n"
    )
    for row in rows:
        pred = (
            f"{row['pred_home']}:{row['pred_away']}"
            if row["pred_home"] is not None
            else "—"
        )
        score = (
            f"{row['result_home']}:{row['result_away']}"
            if row["result_home"] is not None
            else "—"
        )
        points = "" if row["points"] is None else f"  ({row['points']} очк.)"
        text += (
            f"{row['match_number']}. "
            f"{format_match_teams(row['home_team'], row['away_team'], row['home_display_name'], row['away_display_name'], row['home_country_code'], row['away_country_code'], row['home_flag_emoji'], row['away_flag_emoji'])}\n"
            f"   прогноз {pred} | счёт {score}{points}\n"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            back_button("↩️ К турам", f"u:my:t:{round_item['tournament_id']}")
        ]
    )
    await callback.answer()
    chunks = chunk_text(text)
    await send_or_edit(callback, chunks[0], keyboard if len(chunks) == 1 else None)
    for chunk in chunks[1:]:
        await callback.message.answer(chunk)


@router.message(F.text == "🏆 Таблица")
async def table_handler(message: Message):
    db_user = await ensure_user_and_join(message)
    tournaments = await user_tournaments_or_hint(message, db_user)
    if not tournaments:
        await message.answer("Нет турниров для таблицы.")
        return

    if len(tournaments) == 1:
        await send_tournament_table(message, tournaments[0]["id"])
        return

    await message.answer(
        "Выбери турнир:",
        reply_markup=await pick_tournament_keyboard(tournaments, "u:tb:t"),
    )


async def send_tournament_table(target: Message | CallbackQuery, tournament_id: int):
    tournament = await db.get_tournament(tournament_id)
    standings = await db.get_tournament_standings(tournament_id)
    text = format_standings(
        f"🏆 Общая таблица — {tournament['name']} ({tournament['season']})",
        standings,
    )
    chunks = chunk_text(text)
    if isinstance(target, CallbackQuery):
        await send_or_edit(target, chunks[0])
        for chunk in chunks[1:]:
            await target.message.answer(chunk)
    else:
        for chunk in chunks:
            await target.answer(chunk)


@router.callback_query(F.data.startswith("u:tb:t:"))
async def table_tournament_callback(callback: CallbackQuery):
    await send_tournament_table(callback, int(callback.data.split(":")[-1]))


async def send_user_profile(
    target: Message | CallbackQuery,
    tournament_id: int,
    user_id: int,
):
    tournament = await db.get_tournament(tournament_id)
    profile = await db.get_user_profile_stats(tournament_id, user_id)
    standings = await db.get_tournament_standings(tournament_id)
    if tournament is None or profile is None:
        text = "Профиль в этом турнире не найден."
    else:
        position = next(
            (
                index
                for index, row in enumerate(standings, start=1)
                if row["participant_id"] == profile["participant_id"]
            ),
            "—",
        )
        text = (
            f"👤 Профиль · {tournament['name']}\n"
            f"Сезон: {tournament['season']}\n\n"
            f"Место: {position}\n"
            f"Очки: {profile['points']}\n"
            f"Точные счета: {profile['exact']}\n"
            f"Верная разница: {profile['differences']}\n"
            f"Верный исход: {profile['outcomes']}\n"
            f"Прогнозов: {profile['predictions_count']} "
            f"из {profile['matches_count']}"
        )

    if isinstance(target, CallbackQuery):
        await send_or_edit(target, text)
    else:
        await target.answer(text)


@router.message(F.text == "👤 Профиль")
async def profile_handler(message: Message):
    db_user = await ensure_user_and_join(message)
    tournaments = await user_tournaments_or_hint(message, db_user)
    if not tournaments:
        await message.answer("Нет турниров для профиля.")
        return

    if len(tournaments) == 1:
        await send_user_profile(message, tournaments[0]["id"], db_user["id"])
        return

    await message.answer(
        "Выбери турнир:",
        reply_markup=await pick_tournament_keyboard(tournaments, "u:pf:t"),
    )


@router.callback_query(F.data.startswith("u:pf:t:"))
async def profile_tournament_callback(callback: CallbackQuery):
    db_user = await db.get_user(callback.from_user.id)
    if db_user is None:
        await callback.answer("Сначала /start", show_alert=True)
        return
    await send_user_profile(
        callback,
        int(callback.data.split(":")[-1]),
        db_user["id"],
    )


@router.message(F.text == "📚 Архив")
async def archive_handler(message: Message):
    db_user = await ensure_user_and_join(message)
    tournaments = await user_tournaments_or_hint(message, db_user)
    if not tournaments:
        await message.answer("Нет турниров.")
        return

    if len(tournaments) == 1:
        await show_archive_rounds_message(message, tournaments[0]["id"])
        return

    await message.answer(
        "Выбери турнир:",
        reply_markup=await pick_tournament_keyboard(tournaments, "u:ar:t"),
    )


async def show_archive_rounds_message(message: Message, tournament_id: int):
    rounds = await db.get_finished_rounds(tournament_id)
    if not rounds:
        await message.answer("Завершённых туров пока нет.")
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=f"Тур {item['round_number']}",
                callback_data=f"u:ar:r:{item['id']}",
            )
        ]
        for item in rounds
    ]
    await message.answer(
        "📚 Архив туров:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("u:ar:t:"))
async def archive_tournament_callback(callback: CallbackQuery):
    tournament_id = int(callback.data.split(":")[-1])
    rounds = await db.get_finished_rounds(tournament_id)
    if not rounds:
        await send_or_edit(callback, "Завершённых туров пока нет.")
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=f"Тур {item['round_number']}",
                callback_data=f"u:ar:r:{item['id']}",
            )
        ]
        for item in rounds
    ]
    await send_or_edit(
        callback,
        "📚 Архив туров:",
        InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("u:ar:r:"))
async def archive_round_callback(callback: CallbackQuery):
    db_user = await db.get_user(callback.from_user.id)
    round_id = int(callback.data.split(":")[-1])
    round_item = await db.get_round(round_id)
    if db_user is None or round_item is None:
        await callback.answer("Данные не найдены", show_alert=True)
        return

    standings = await db.get_round_standings(round_id)
    table = format_standings(
        f"📚 Архив — Тур {round_item['round_number']}",
        standings,
    )

    participant = await db.get_participant(
        round_item["tournament_id"],
        db_user["id"],
    )
    extra = ""
    if participant:
        rows = await db.get_user_predictions_for_round(
            participant["id"],
            round_id,
        )
        extra = "\n\nТвои прогнозы:\n"
        for row in rows:
            pred = (
                f"{row['pred_home']}:{row['pred_away']}"
                if row["pred_home"] is not None
                else "—"
            )
            score = (
                f"{row['result_home']}:{row['result_away']}"
                if row["result_home"] is not None
                else "—"
            )
            points = "—" if row["points"] is None else str(row["points"])
            extra += (
                f"{row['match_number']}. {row['home_team']} — {row['away_team']}: "
                f"прогноз {pred} / счёт {score} ({points} очк.)\n"
            )

    text = table + extra
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            back_button("↩️ К архиву", f"u:ar:t:{round_item['tournament_id']}")
        ]
    )
    chunks = chunk_text(text)
    await callback.answer()
    await send_or_edit(callback, chunks[0], keyboard if len(chunks) == 1 else None)
    for chunk in chunks[1:]:
        await callback.message.answer(chunk)
