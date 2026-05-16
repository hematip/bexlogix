"""End-to-end tests for the assignment pipeline: generate, publish,
visit submission, flush, and the batched schedule-state rebuild."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.visit_result import VisitResult
from server.app.errors import DomainError
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import assignment_service, visit_service


WORK_DATE = date(2026, 5, 15)


def _seed_world(db, n_visitors: int = 2, n_stores: int = 6):
    """Seed manager + visitors + stores + per-day status. Return ids."""
    manager = User(username="m1", password_hash="x", role="manager", is_active=True)
    db.add(manager)
    db.flush()

    visitor_ids: list[int] = []
    for i in range(n_visitors):
        user = User(username=f"v{i}", password_hash="x", role="visitor", is_active=True)
        db.add(user)
        db.flush()
        profile = VisitorProfile(
            user_id=user.id,
            visitor_code=f"VIS-{i:03d}",
            full_name=f"V{i}",
            default_start_lat=35.70 + i * 0.01,
            default_start_lon=51.30 + i * 0.01,
            default_capacity=30,
            is_active=True,
        )
        db.add(profile)
        db.flush()
        db.add(DailyVisitorStatus(
            visitor_id=profile.id,
            work_date=WORK_DATE,
            start_lat=profile.default_start_lat,
            start_lon=profile.default_start_lon,
            capacity=30,
            is_active_today=True,
        ))
        visitor_ids.append(profile.id)

    store_ids: list[int] = []
    for i in range(n_stores):
        store = Store(
            store_code=f"STR-{i:03d}",
            store_name=f"S{i}",
            region="مرکز",
            lat=35.70 + 0.005 * i,
            lon=51.30 + 0.005 * i,
            grade="A+",
            has_confectionery=True,
            has_oil=False,
            has_pasta=False,
        )
        db.add(store)
        db.flush()
        store_ids.append(store.id)

    db.commit()
    return {
        "manager_id": manager.id,
        "visitor_ids": visitor_ids,
        "store_ids": store_ids,
    }


class TestGenerateDraftAssignments:
    def test_assigns_all_due_stores_with_legacy_solver(self, db_session, monkeypatch):
        # Force the legacy NN path; VROOM is not available in test env.
        from server.app import config as app_config
        monkeypatch.setattr(app_config, "ROUTING_SOLVER_MODE", "legacy", raising=False)

        ids = _seed_world(db_session, n_visitors=2, n_stores=6)

        result = assignment_service.generate_draft_assignments(
            db=db_session,
            work_date=WORK_DATE,
            manager_user_id=ids["manager_id"],
        )

        assert result["due_stores"] == 6
        assert result["created_assignments"] == 6
        assert result["unassigned_due_stores"] == 0

        all_assignments = (
            db_session.query(DailyAssignment)
            .filter(DailyAssignment.work_date == WORK_DATE)
            .all()
        )
        assert len(all_assignments) == 6
        assert all(a.assignment_status == AssignmentStatus.DRAFT.value for a in all_assignments)

        # Each store assigned exactly once thanks to the unique constraint.
        store_ids_in_assignments = sorted(a.store_id for a in all_assignments)
        assert store_ids_in_assignments == sorted(ids["store_ids"])

    def test_blocks_regeneration_when_non_draft_exists(self, db_session, monkeypatch):
        from server.app import config as app_config
        monkeypatch.setattr(app_config, "ROUTING_SOLVER_MODE", "legacy", raising=False)

        ids = _seed_world(db_session, n_visitors=2, n_stores=4)
        assignment_service.generate_draft_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )
        # Promote everything to PUBLISHED manually.
        db_session.query(DailyAssignment).update(
            {DailyAssignment.assignment_status: AssignmentStatus.PUBLISHED.value}
        )
        db_session.commit()

        with pytest.raises(DomainError):
            assignment_service.generate_draft_assignments(
                db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
            )


class TestPublishConcurrency:
    def test_second_publish_call_is_a_noop_via_domain_error(self, db_session, monkeypatch):
        from server.app import config as app_config
        monkeypatch.setattr(app_config, "ROUTING_SOLVER_MODE", "legacy", raising=False)

        ids = _seed_world(db_session, n_visitors=1, n_stores=3)
        assignment_service.generate_draft_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )
        # Approve all drafts.
        db_session.query(DailyAssignment).update(
            {DailyAssignment.assignment_status: AssignmentStatus.SUPERVISOR_APPROVED.value}
        )
        db_session.commit()

        count_first = assignment_service.publish_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )
        assert count_first == 3

        # A second call now has nothing in SUPERVISOR_APPROVED state — the
        # list_assignments_for_publish read returns empty, which raises the
        # documented domain error rather than silently overwriting.
        with pytest.raises(DomainError):
            assignment_service.publish_assignments(
                db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
            )


class TestVisitSubmissionConcurrency:
    def test_second_submit_for_same_assignment_is_rejected(self, db_session, monkeypatch):
        from server.app import config as app_config
        monkeypatch.setattr(app_config, "ROUTING_SOLVER_MODE", "legacy", raising=False)

        ids = _seed_world(db_session, n_visitors=1, n_stores=1)
        assignment_service.generate_draft_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )
        db_session.query(DailyAssignment).update(
            {DailyAssignment.assignment_status: AssignmentStatus.SUPERVISOR_APPROVED.value}
        )
        db_session.commit()
        assignment_service.publish_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )

        assignment = db_session.query(DailyAssignment).first()
        visitor_user_id = (
            db_session.query(VisitorProfile.user_id)
            .filter(VisitorProfile.id == assignment.visitor_id)
            .scalar()
        )

        visit_service.submit_visit_result(
            db=db_session,
            assignment_id=assignment.id,
            visitor_user_id=visitor_user_id,
            result=VisitResult.GREEN.value,
            note=None,
        )

        # Reset the assignment status to PUBLISHED to bypass the existence
        # check and exercise the DB-level guard.
        db_session.query(DailyAssignment).filter(DailyAssignment.id == assignment.id).update(
            {DailyAssignment.assignment_status: AssignmentStatus.PUBLISHED.value}
        )
        db_session.commit()

        with pytest.raises(DomainError):
            visit_service.submit_visit_result(
                db=db_session,
                assignment_id=assignment.id,
                visitor_user_id=visitor_user_id,
                result=VisitResult.YELLOW.value,
                note=None,
            )


class TestBatchedRebuild:
    def test_flush_recomputes_schedule_state_for_all_affected_stores(
        self, db_session, monkeypatch
    ):
        from server.app import config as app_config
        monkeypatch.setattr(app_config, "ROUTING_SOLVER_MODE", "legacy", raising=False)

        ids = _seed_world(db_session, n_visitors=1, n_stores=4)
        assignment_service.generate_draft_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )
        db_session.query(DailyAssignment).update(
            {DailyAssignment.assignment_status: AssignmentStatus.SUPERVISOR_APPROVED.value}
        )
        db_session.commit()
        assignment_service.publish_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )

        # Submit a green visit for each assignment.
        assignments = db_session.query(DailyAssignment).all()
        visitor_user_id = (
            db_session.query(VisitorProfile.user_id)
            .filter(VisitorProfile.id == assignments[0].visitor_id)
            .scalar()
        )
        for a in assignments:
            visit_service.submit_visit_result(
                db=db_session,
                assignment_id=a.id,
                visitor_user_id=visitor_user_id,
                result=VisitResult.GREEN.value,
                note=None,
            )

        # Each store should now have next_visit_date pushed +6 days (A+ interval).
        states_before_flush = {
            s.store_id: s.next_visit_date
            for s in db_session.query(StoreScheduleState).all()
        }
        for store_id in ids["store_ids"]:
            assert states_before_flush[store_id] == WORK_DATE + timedelta(days=6)

        # Flush the day.
        result = assignment_service.flush_work_date_operational_data(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )
        assert result["affected_stores"] == 4
        assert result["assignments_deleted"] == 4
        assert result["visits_deleted"] == 4

        # After flush, replay finds no events ⇒ baseline state.
        states_after_flush = {
            s.store_id: s for s in db_session.query(StoreScheduleState).all()
        }
        for store_id in ids["store_ids"]:
            s = states_after_flush[store_id]
            assert s.last_visit_date is None
            assert s.last_visit_result is None
            assert s.next_visit_date == WORK_DATE
            assert s.in_telesales_queue is False

    def test_batch_query_count_is_bounded(self, db_session, monkeypatch):
        """Ensure the rebuild emits a fixed number of SQL queries
        regardless of the number of affected stores. Production-readiness
        regression guard for the O(N) → O(1) refactor."""
        from sqlalchemy import event

        from server.app import config as app_config
        monkeypatch.setattr(app_config, "ROUTING_SOLVER_MODE", "legacy", raising=False)

        ids = _seed_world(db_session, n_visitors=2, n_stores=20)

        assignment_service.generate_draft_assignments(
            db=db_session, work_date=WORK_DATE, manager_user_id=ids["manager_id"]
        )
        db_session.query(DailyAssignment).update(
            {DailyAssignment.assignment_status: AssignmentStatus.SUPERVISOR_APPROVED.value}
        )
        db_session.commit()

        query_count = 0
        engine = db_session.get_bind()

        @event.listens_for(engine, "before_cursor_execute")
        def _count(_conn, _cursor, _statement, _params, _ctx, _execmany):
            nonlocal query_count
            query_count += 1

        try:
            assignment_service._rebuild_store_schedule_states_for_stores(
                db=db_session,
                store_ids=ids["store_ids"],
                baseline_date=WORK_DATE,
            )
            db_session.commit()
        finally:
            event.remove(engine, "before_cursor_execute", _count)

        # The implementation must do a fixed number of queries regardless of
        # how many stores are affected. A handful of SELECTs + a flush is
        # acceptable; many dozens per store is a regression.
        assert query_count < 15, (
            f"rebuild used {query_count} queries for 20 stores; expected O(1)"
        )
