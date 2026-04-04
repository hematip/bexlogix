# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import datetime, timezone

from server.app.enums.roles import UserRole
from server.app.models.user import User
from server.app.models.visitor_profile import VisitorProfile
from server.db.database import get_db_session

#
# Contract: main executes one deterministic step in the workflow.
def main():
    db = get_db_session()
    try:
        for i in range(1, 11):
            username = f"visitor{i}"

            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                continue

            user = User(
                username=username,
                password_hash="temp_hash_for_now",
                role=UserRole.VISITOR.value,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.flush()

            profile = VisitorProfile(
                user_id=user.id,
                visitor_code=f"VIS-{i:03}",
                full_name=f"Visitor {i}",
                default_start_lat=35.7000 + (i * 0.01),
                default_start_lon=51.3500 + (i * 0.01),
                default_capacity=30,
                is_active=True,
            )
            db.add(profile)

        db.commit()
        print("Visitor users and profiles seeded successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
