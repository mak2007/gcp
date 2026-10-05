import asyncio
import os
import sys

# Configure UTF-8 for console output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import database as db

async def run_tests():
    print("[*] Running database & logic tests...")
    
    # Use a test database
    db.DB_PATH = "test_bot.sqlite"
    if os.path.exists("test_bot.sqlite"):
        os.remove("test_bot.sqlite")

    await db.init_db()
    print("✅ Database initialized.")

    # 1. Test duplicate email validation
    email1 = "testuser@example.com"
    is_registered = await db.is_email_registered(email1)
    assert not is_registered, "Email should not be registered initially"

    # Create first submission
    sub1_id = await db.create_submission(
        user_id=111,
        username="user_one",
        full_name="Alice Smith",
        email=email1,
        unique_code="CODE123"
    )
    print(f"✅ Created submission #1 (ID: {sub1_id})")

    # Check duplicate email rejection
    assert await db.is_email_registered(email1), "Email should be registered now"
    assert await db.is_email_registered("TESTUSER@example.com"), "Case-insensitive match must work"
    assert await db.is_email_registered("  testuser@example.com  "), "Whitespace strip match must work"
    print("✅ Duplicate email checks passed: duplicate emails are immediately recognized!")

    # 2. Test Queue Calculation
    # Add 9 more submissions to have exactly 10 people submitted before Bob
    for i in range(2, 11):
        await db.create_submission(
            user_id=100 + i,
            username=f"user_{i}",
            full_name=f"User {i}",
            email=f"user{i}@example.com",
            unique_code=f"CODE_{i}"
        )

    # Now create the 11th user after 10 people
    sub11_id = await db.create_submission(
        user_id=999,
        username="user_eleven",
        full_name="Bob Eleventh",
        email="bob11@example.com",
        unique_code="CODE_ELEVEN"
    )

    q_info = await db.get_queue_info(sub11_id)
    print(f"Queue info for 11th submission: {q_info}")
    assert q_info["position"] == 11, f"Expected position 11, got {q_info['position']}"
    assert q_info["ahead_count"] == 10, f"Expected 10 ahead, got {q_info['ahead_count']}"
    assert q_info["total_pending"] == 11, f"Expected 11 total pending, got {q_info['total_pending']}"
    print("✅ Queue calculation passed: 11th submitter sees position #11 and 10 ahead!")

    # 3. Test status transitions
    # In Review
    updated = await db.update_submission_status(sub1_id, "IN_REVIEW")
    assert updated["status"] == "IN_REVIEW"
    print("✅ Status transition to IN_REVIEW passed.")

    # When sub1 is IN_REVIEW, pending queue should decrease by 1
    q_info_after = await db.get_queue_info(sub11_id)
    assert q_info_after["position"] == 10, f"Expected position 10 after sub1 moved, got {q_info_after['position']}"
    assert q_info_after["ahead_count"] == 9
    print("✅ Dynamic queue update passed: queue updates in real-time as admin reviews!")

    # Accepted
    updated_accepted = await db.update_submission_status(sub1_id, "ACCEPTED")
    assert updated_accepted["status"] == "ACCEPTED"
    print("✅ Status transition to ACCEPTED passed.")

    # 4. Test Resubmission
    sub_resubmit = await db.create_submission(
        user_id=555,
        username="resubmitter",
        full_name="Charlie Brown",
        email="charlie@example.com",
        unique_code="OLD_CODE"
    )
    await db.update_submission_status(sub_resubmit, "CAN_RESUBMIT", "Code was invalid")
    check_sub = await db.get_submission_by_id(sub_resubmit)
    assert check_sub["status"] == "CAN_RESUBMIT"

    # User resubmits with new code and email
    await db.update_submission_resubmit(sub_resubmit, "Charlie Brown", "charlie_new@example.com", "NEW_CODE_999")
    re_sub = await db.get_submission_by_id(sub_resubmit)
    assert re_sub["status"] == "PENDING"
    assert re_sub["unique_code"] == "NEW_CODE_999"
    assert re_sub["email"] == "charlie_new@example.com"
    print("✅ Resubmission flow passed.")

    # 5. Test Appeal
    appeal_id = await db.create_appeal(sub_resubmit, 555, "I submitted the wrong screenshot code, here is proof.")
    assert appeal_id is not None
    pending_appeals = await db.get_pending_appeals()
    assert len(pending_appeals) == 1
    assert pending_appeals[0]["id"] == appeal_id

    # Resolve appeal
    await db.update_appeal_status(appeal_id, "APPROVED", "Accepted by admin")
    app_obj = await db.get_appeal_by_id(appeal_id)
    assert app_obj["status"] == "APPROVED"
    print("✅ Appeal system passed.")

    # 6. Test Support message
    sup_id = await db.save_support_message(555, "resubmitter", "Need help with payment method")
    assert sup_id is not None
    print("✅ Support messages passed.")

    # 7. Test Admin Stats
    stats = await db.get_admin_stats()
    print(f"Stats: {stats}")
    assert stats["total"] > 0
    # 8. Test User Registration & Broadcast targeting
    await db.register_user(777, "broadcast_user1", "Dave")
    await db.register_user(888, "broadcast_user2", "Eve")
    all_users = await db.get_all_user_ids()
    assert 777 in all_users
    assert 888 in all_users
    total_users_count = await db.get_total_users_count()
    assert total_users_count >= 2
    print(f"✅ User registration & broadcast targeting passed: {total_users_count} total users reach.")

    # Cleanup test db
    if os.path.exists("test_bot.sqlite"):
        os.remove("test_bot.sqlite")

    print("\n🎉 ALL 8 TEST SUITES PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
