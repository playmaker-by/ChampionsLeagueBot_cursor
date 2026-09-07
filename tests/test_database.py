import os
import tempfile
import unittest

from database import Database
from utils import utc_now_str


class DatabaseFlowTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.db = Database(self.path)
        await self.db.create_tables()

    async def asyncTearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    async def test_match_crud_and_scoring(self):
        tournament_id = await self.db.create_tournament("UCL", "2026/27")
        await self.db.create_round(tournament_id, 1)
        rounds = await self.db.get_rounds(tournament_id)
        round_id = rounds[0]["id"]

        match_id = await self.db.create_match(
            round_id=round_id,
            match_number=1,
            home_team="Арсенал",
            away_team="Наполи",
            kickoff_at="2099-01-01 12:00:00",
        )
        match = await self.db.get_match(match_id)
        self.assertEqual(match["home_team"], "Арсенал")
        self.assertFalse(self.db.match_locked_for_admin(match))

        tournament = await self.db.get_tournament(tournament_id)
        self.assertEqual(tournament["status"], "active")

        await self.db.update_match(
            match_id,
            2,
            "Арсенал",
            "Наполи",
            "2099-01-01 15:00:00",
        )
        match = await self.db.get_match(match_id)
        self.assertEqual(match["match_number"], 2)

        user = await self.db.create_or_update_user(1001, "ivan", "Иван", None)
        await self.db.ensure_participant(tournament_id, user["id"])
        participant = await self.db.get_participant(tournament_id, user["id"])
        await self.db.upsert_prediction(participant["id"], match_id, 2, 1)

        await self.db.set_match_result(match_id, 2, 1)
        match = await self.db.get_match(match_id)
        self.assertEqual(match["status"], "finished")
        self.assertTrue(self.db.match_locked_for_admin(match))

        standings = await self.db.get_round_standings(round_id)
        self.assertEqual(standings[0]["points"], 3)
        self.assertEqual(standings[0]["exact"], 1)

        table = await self.db.get_tournament_standings(tournament_id)
        self.assertEqual(table[0]["points"], 3)

        await self.db.set_match_result(match_id, 0, 0)
        standings = await self.db.get_round_standings(round_id)
        self.assertEqual(standings[0]["points"], 0)

        round_item = await self.db.get_round(round_id)
        self.assertEqual(round_item["status"], "finished")

    async def test_delete_match_and_lock_started(self):
        tournament_id = await self.db.create_tournament("UCL", "2026/27")
        await self.db.create_round(tournament_id, 1)
        round_id = (await self.db.get_rounds(tournament_id))[0]["id"]
        match_id = await self.db.create_match(
            round_id,
            1,
            "А",
            "Б",
            "2019-01-01 00:00:00",
        )
        closed = await self.db.lock_started_matches(round_id)
        self.assertEqual(closed, 1)
        match = await self.db.get_match(match_id)
        self.assertEqual(match["status"], "live")
        self.assertTrue(self.db.match_locked_for_admin(match))

        future_id = await self.db.create_match(
            round_id,
            2,
            "В",
            "Г",
            "2099-01-01 00:00:00",
        )
        await self.db.delete_match(future_id)
        self.assertIsNone(await self.db.get_match(future_id))

    async def test_group_bind_and_participants(self):
        tournament_id = await self.db.create_tournament("UCL", "2026/27")
        await self.db.bind_group(-100, "Чат", tournament_id)
        groups = await self.db.get_active_groups(tournament_id)
        self.assertEqual(len(groups), 1)

        user = await self.db.create_or_update_user(7, "bob", "Bob", "Lee")
        await self.db.join_user_to_open_tournaments(user["id"])
        people = await self.db.get_participants(tournament_id)
        self.assertEqual(len(people), 1)

        await self.db.set_participant_active(people[0]["id"], 0)
        people = await self.db.get_participants(tournament_id)
        self.assertEqual(people[0]["is_active"], 0)

        self.assertTrue(utc_now_str())

    async def test_locked_prediction_is_not_overwritten(self):
        tournament_id = await self.db.create_tournament("UCL", "2026/27")
        await self.db.create_round(tournament_id, 1)
        round_id = (await self.db.get_rounds(tournament_id))[0]["id"]
        match_id = await self.db.create_match(
            round_id,
            1,
            "А",
            "Б",
            "2099-01-01 00:00:00",
        )
        user = await self.db.create_or_update_user(9, "ann", "Ann", None)
        await self.db.ensure_participant(tournament_id, user["id"])
        participant = await self.db.get_participant(tournament_id, user["id"])
        self.assertTrue(
            await self.db.upsert_prediction(participant["id"], match_id, 1, 0)
        )
        prediction = await self.db.get_prediction(participant["id"], match_id)
        await self.db.lock_prediction(prediction["id"])
        self.assertFalse(
            await self.db.upsert_prediction(participant["id"], match_id, 5, 5)
        )
        prediction = await self.db.get_prediction(participant["id"], match_id)
        self.assertEqual(prediction["home_score"], 1)
        self.assertEqual(prediction["away_score"], 0)


if __name__ == "__main__":
    unittest.main()
