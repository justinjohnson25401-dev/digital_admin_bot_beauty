# AI Bug Tracker

| ID | Bug Description | Priority | Status | Date Found | Date Fixed | Session Notes |
|:---|:---|:---|:---|:---|:---|:---|
| 001 | **Race Condition in Booking Confirmation:** If two users try to book the same slot simultaneously, the first user succeeds, but the second user's session hangs or crashes because an unhandled `ValueError` is raised from the database layer. The user receives no feedback. | **Critical** | **Fixed** | 2024-05-21 | 2024-05-21 | The bug was fixed by implementing `try...except` error handling in `handlers/booking/confirmation.py` and adding a user-friendly error message. See Session 2024-05-21 in `CHANGELOG_AI.md`. |
