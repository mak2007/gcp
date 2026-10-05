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
        email=email1,
        pass_code="PASS123",
        key_code="KEY123"
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
            email=f"user{i}@example.com",
            pass_code=f"PASS_{i}",
            key_code=f"KEY_{i}"
        )

    # Now create the 11th user after 10 people
    sub11_id = await db.create_submission(
        user_id=999,
        username="user_eleven",
        email="bob11@example.com",
        pass_code="BOB_PASS",
        key_code="BOB_KEY"
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
        email="charlie@example.com",
        pass_code="OLD_PASS",
        key_code="OLD_KEY"
    )
    await db.update_submission_status(sub_resubmit, "CAN_RESUBMIT", "Code was invalid")
    check_sub = await db.get_submission_by_id(sub_resubmit)
    assert check_sub["status"] == "CAN_RESUBMIT"

    # User resubmits with new code and email
    await db.update_submission_resubmit(sub_resubmit, "charlie_new@example.com", "NEW_PASS_999", "NEW_KEY_999")
    re_sub = await db.get_submission_by_id(sub_resubmit)
    assert re_sub["status"] == "PENDING"
    assert re_sub["pass_code"] == "NEW_PASS_999"
    assert re_sub["key_code"] == "NEW_KEY_999"
    assert re_sub["email"] == "charlie_new@example.com"
    assert re_sub["is_resubmission"] == 1, "is_resubmission must be 1"
    assert re_sub["resubmitted_at"] is not None, "resubmitted_at must be populated"

    resub_list = await db.get_resubmitted_submissions()
    assert len(resub_list) >= 1
    assert any(r["id"] == sub_resubmit for r in resub_list)
    assert await db.get_resubmitted_count() >= 1
    print("✅ Resubmission flow and dedicated list passed.")

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
    assert stats["resubmitted"] >= 1, "Admin stats must include resubmitted count"
    print("✅ Admin stats include resubmitted count passed.")

    # 8. Test User Registration & Broadcast targeting
    await db.register_user(777, "broadcast_user1", "Dave")
    await db.register_user(888, "broadcast_user2", "Eve")
    all_users = await db.get_all_user_ids()
    assert 777 in all_users
    assert 888 in all_users
    total_users_count = await db.get_total_users_count()
    assert total_users_count >= 2
    print(f"✅ User registration & broadcast targeting passed: {total_users_count} total users reach.")

    # 9. Test Multiple Submissions per user
    user_multi_id = 9999
    await db.create_submission(user_multi_id, "multi_user", "batch1@gmail.com", "P1", "K1")
    await db.create_submission(user_multi_id, "multi_user", "batch2@gmail.com", "P2", "K2")
    await db.create_submission(user_multi_id, "multi_user", "batch3@gmail.com", "P3", "K3")
    user_subs = await db.get_all_submissions_by_user(user_multi_id)
    assert len(user_subs) == 3
    print(f"✅ Multiple submissions per user verified: user has {len(user_subs)} active submissions!")

    # 10. Test 8-Hour Cooldown Logic
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)

    # Submitted 2 hours ago: cooldown active
    time_2h_ago = (now_utc - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S UTC")
    can_resub, rem_h, rem_m = db.check_8_hour_cooldown(time_2h_ago)
    assert not can_resub, "Should not be able to resubmit within 8 hours"
    assert rem_h == 5 or rem_h == 6, f"Expected ~5-6h remaining, got {rem_h}"

    # Submitted 7 hours 45 mins ago: cooldown active
    time_almost = (now_utc - timedelta(hours=7, minutes=45)).strftime("%Y-%m-%d %H:%M:%S UTC")
    can_resub2, rem_h2, rem_m2 = db.check_8_hour_cooldown(time_almost)
    assert not can_resub2
    assert rem_h2 == 0
    assert 10 <= rem_m2 <= 16

    # Submitted 8 hours 5 mins ago: cooldown passed
    time_passed = (now_utc - timedelta(hours=8, minutes=5)).strftime("%Y-%m-%d %H:%M:%S UTC")
    can_resub3, rem_h3, rem_m3 = db.check_8_hour_cooldown(time_passed)
    assert can_resub3, "Should be able to resubmit after 8 hours"
    assert rem_h3 == 0 and rem_m3 == 0
    print("✅ 8-hour cooldown calculation logic passed.")

    # 11. Test Admin-Unlock requirement & Post-Unlock Cooldown
    sub_test_unlock = await db.create_submission(1234, "tester", "locked@example.com", "PASS", "KEY")
    sub_obj = await db.get_submission_by_id(sub_test_unlock)
    can_res, reason, _, _ = db.check_resubmit_eligibility(sub_obj)
    assert not can_res and reason == "NOT_UNLOCKED", "Resubmission must be blocked if admin did not unlock"

    # Admin clicks 'Can Resubmit' now
    await db.update_submission_status(sub_test_unlock, "CAN_RESUBMIT", "Fix your key")
    sub_obj_unlocked = await db.get_submission_by_id(sub_test_unlock)
    assert sub_obj_unlocked["resubmit_unlocked_at"] is not None
    # Just unlocked -> cooldown is active
    can_res2, reason2, h2, m2 = db.check_resubmit_eligibility(sub_obj_unlocked)
    assert not can_res2 and reason2 == "COOLDOWN_ACTIVE", "Cooldown must be active right after admin clicks"

    # Simulate 8 hours passed since admin unlocked
    fake_unlock_time = (now_utc - timedelta(hours=8, minutes=10)).strftime("%Y-%m-%d %H:%M:%S UTC")
    sub_obj_unlocked["resubmit_unlocked_at"] = fake_unlock_time
    can_res3, reason3, _, _ = db.check_resubmit_eligibility(sub_obj_unlocked)
    assert can_res3 and reason3 == "ELIGIBLE", "Must be eligible once 8 hours have passed since admin unlocked"
    print("✅ Admin-unlock requirement and 8-hour post-unlock cooldown verified.")

    # 12. Test Undo Action (Revert to PENDING)
    sub_undo_id = await db.create_submission(5678, "undo_user", "undo@example.com", "P", "K")
    # Admin mistakenly moves to IN_REVIEW
    await db.update_submission_status(sub_undo_id, "IN_REVIEW")
    chk = await db.get_submission_by_id(sub_undo_id)
    assert chk["status"] == "IN_REVIEW"

    # Admin clicks Undo -> reverts to PENDING
    await db.update_submission_status(sub_undo_id, "PENDING")
    chk_undone = await db.get_submission_by_id(sub_undo_id)
    assert chk_undone["status"] == "PENDING"

    # Admin mistakenly moves to ACCEPTED
    await db.update_submission_status(sub_undo_id, "ACCEPTED")
    chk2 = await db.get_submission_by_id(sub_undo_id)
    assert chk2["status"] == "ACCEPTED"

    # Admin clicks Undo -> reverts to PENDING
    await db.update_submission_status(sub_undo_id, "PENDING")
    chk_undone2 = await db.get_submission_by_id(sub_undo_id)
    assert chk_undone2["status"] == "PENDING"
    print("✅ Admin Undo action (revert to PENDING) verified.")

    # 13. Test Inventory Statistics Breakdown
    stats_inv = await db.get_admin_stats()
    assert "new_total" in stats_inv
    assert "new_pending" in stats_inv
    assert "resubmitted_total" in stats_inv
    assert "resubmitted_pending" in stats_inv
    assert stats_inv["new_total"] > 0
    print(f"✅ Investor/Inventory stock stats verified: New={stats_inv['new_total']} (Pending={stats_inv['new_pending']}), Resubmitted={stats_inv['resubmitted_total']}")

    # 14. Test Custom TXT Batch Query
    batch_5 = await db.get_submissions_batch(limit=5, status="PENDING")
    assert len(batch_5) == 5, f"Expected 5 submissions in batch, got {len(batch_5)}"
    batch_3 = await db.get_submissions_batch(limit=3, status="PENDING")
    assert len(batch_3) == 3
    print("✅ Custom batch pool selection verified.")

    # 15. Test Dynamic Bot Settings (Channel, Video, Support Handle)
    # Default fallbacks
    init_channel = await db.get_channel_url()
    init_video = await db.get_video_url()
    init_support = await db.get_support_handle()
    assert init_channel is not None and len(init_channel) > 0
    assert init_video is not None and len(init_video) > 0
    assert init_support is not None and len(init_support) > 0

    # Live update via set_setting
    await db.set_setting("channel_url", "https://t.me/MyNewChannel123")
    await db.set_setting("video_url", "https://t.me/MyTutorialVideo")
    await db.set_setting("support_handle", "@MySupportAdmin")

    assert await db.get_channel_url() == "https://t.me/MyNewChannel123"
    assert await db.get_video_url() == "https://t.me/MyTutorialVideo"
    assert await db.get_support_handle() == "@MySupportAdmin"
    print("✅ Dynamic Bot Settings (Channel, Video, Support Handle) persistence and live retrieval verified.")

    # 16. Test Category Separation for Approved & Disapproved Submissions
    acc_sub_id = await db.create_submission(9991, "approved_u", "approved@test.com", "P", "K")
    await db.update_submission_status(acc_sub_id, "ACCEPTED")
    dis_sub_id = await db.create_submission(9992, "disapproved_u", "disapproved@test.com", "P", "K")
    await db.update_submission_status(dis_sub_id, "DISAPPROVED", admin_notes="Invalid unique code")

    approved_list = await db.get_submissions_by_status("ACCEPTED")
    assert any(s["id"] == acc_sub_id for s in approved_list), "Approved submission must appear in ACCEPTED category"

    disapproved_list = await db.get_submissions_by_status("DISAPPROVED")
    assert any(s["id"] == dis_sub_id for s in disapproved_list), "Disapproved submission must appear in DISAPPROVED category"
    print("✅ Category isolation (Approved vs Disapproved) verified.")

    # Cleanup test db
    if os.path.exists("test_bot.sqlite"):
        os.remove("test_bot.sqlite")

    print("\n🎉 ALL 16 TEST SUITES PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
