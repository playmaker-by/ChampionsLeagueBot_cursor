from aiogram.fsm.state import State, StatesGroup


class CreateTournament(StatesGroup):
    name = State()
    season = State()


class AddMatches(StatesGroup):
    matches = State()


class EditMatch(StatesGroup):
    data = State()


class AddSingleMatch(StatesGroup):
    data = State()


class BindGroup(StatesGroup):
    chat_id = State()


class EnterPrediction(StatesGroup):
    score = State()


class EnterResult(StatesGroup):
    score = State()
