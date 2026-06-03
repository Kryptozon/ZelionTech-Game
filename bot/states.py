from aiogram.fsm.state import State, StatesGroup


class ProofFlow(StatesGroup):
    waiting_handle = State()
    waiting_screenshot = State()


class RejectFlow(StatesGroup):
    waiting_reason = State()


class BroadcastFlow(StatesGroup):
    waiting_message = State()
