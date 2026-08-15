# Wire LUCIUS into ORELIUS shared memory

LUCIUS is a Python LiveKit voice agent. These changes push what LUCIUS does into
ORELIUS's shared memory and pull ORELIUS's recent activity back — so the two share
one brain. **No restructuring** — one new file, a few one-line additions.

## 1. Add the bridge file
Copy `orelius_bridge.py` (in this folder) into the **LUCIUS project root** (next to
`agent.py` and `tools.py`).

## 2. Add to LUCIUS `.env`
```
ORELIUS_URL=https://orelius.onrender.com
ORELIUS_SHARED_SECRET=OreliusLucius2026
```
(`ORELIUS_SHARED_SECRET` must match the value set on ORELIUS in Render.)

## 3. Edits to `tools.py`

**a) `memory_store` — mirror every memory into ORELIUS.**
Find the end of `memory_store`:
```python
    from memory.provider import store_async
    return await store_async(role, content, importance, category)
```
Change to:
```python
    from memory.provider import store_async
    result = await store_async(role, content, importance, category)
    from orelius_bridge import remember
    await remember(f"{role}: {content}", kind="memory",
                   meta={"importance": importance, "category": category})
    return result
```

**b) `create_calendar_event` — tell ORELIUS about bookings.**
Just before `return {"status": "created", "event_id": created["id"]}`, add:
```python
    from orelius_bridge import remember
    await remember(f"Booked '{summary}' at {start_time}", kind="appointment",
                   meta={"event_id": created.get("id"), "notify_email": notify_email})
```

**c) `cancel_calendar_event` — tell ORELIUS about cancellations.**
Just before `return f"Event '{event['summary']}' successfully cancelled."`, add:
```python
    from orelius_bridge import remember
    await remember(f"Cancelled '{event['summary']}'", kind="appointment_cancel")
```

**d) `start_greece_call` — log outbound calls.**
Right after `_append_pending_call(call_id, ...)` (just before the
`return f"GREECE outbound call started. call_id={call_id}"`), add:
```python
        from orelius_bridge import remember
        await remember(f"Started GREECE call to {first_name} ({intent})", kind="call",
                       meta={"call_id": call_id, "to_number": to_number})
```

**e) `sync_greece_calls_to_calendar` — log booked appointments from calls.**
Right after `_remove_pending_call(call_id)` in the successful-booking block
(the one that appends `"{call_id}: ✅ booked ..."`), add:
```python
            from orelius_bridge import remember
            await remember(f"GREECE booked {name} ({intent}) at {start_iso}", kind="appointment",
                           meta={"call_id": call_id, "phone": str(phone)})
```

## 4. Edit to `agent.py` — LUCIUS reads ORELIUS's activity

Replace:
```python
def load_persistent_context() -> str:
    return load_session_context(limit=12)
```
with:
```python
def load_persistent_context() -> str:
    ctx = load_session_context(limit=12)
    try:
        from orelius_bridge import recall_text_sync
        shared = recall_text_sync(limit=8)
        if shared:
            ctx = (ctx + "\n\n" + shared) if ctx else shared
    except Exception:
        pass
    return ctx
```

That's it. Restart LUCIUS. Now:
- Everything LUCIUS remembers, books, calls, or cancels → appears in ORELIUS instantly.
- Everything ORELIUS did → shows up in LUCIUS's context at the start of each session.

## Notes
- All bridge calls are **best-effort** and never raise — if ORELIUS is unreachable,
  LUCIUS keeps working and the event is skipped.
- ORELIUS on Render's free tier sleeps after ~15 min idle; the bridge uses a 20s
  write timeout + one retry to survive the wake. If you want zero misses, keep
  ORELIUS warm (a periodic ping) or use a paid instance.
- Optional (persona): if you want LUCIUS to *mention* the shared link, add a line to
  its prompt like: "You share a live memory with ORELIUS; anything either of you
  does, both know." Send me `prompts.py` and I'll drop it in.
