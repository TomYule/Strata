// Ten minutes is a checkpoint, not a blind cancellation deadline.
export function createWatchdog({
  defaultMs = 600000, recheckMs = 120000, now = () => performance.now(),
  schedule = (fn, ms) => setTimeout(fn, ms), unschedule = clearTimeout,
  onCheck, record = () => {},
}) {
  const calls = new Map();
  const waits = new Map();
  const terminal = new Set();
  let closed = false;
  const keyOf = (session, call) => `${session}:${call}`;
  const waiting = (session) => (waits.get(session)?.size || 0) > 0;
  const log = (kind, entry, extra = {}) => record({ kind, sessionID: entry.sessionID,
    callID: entry.callID, messageID: entry.messageID, tool: entry.tool, ...extra });

  function elapsed(entry) {
    return entry.elapsed + (entry.started === null ? 0 : Math.max(0, now() - entry.started));
  }
  function stopTimer(entry) {
    if (entry.timer !== null) unschedule(entry.timer);
    entry.timer = null;
  }
  function pause(entry) {
    stopTimer(entry);
    entry.elapsed = elapsed(entry);
    entry.started = null;
  }
  function arm(entry) {
    stopTimer(entry);
    if (closed || waiting(entry.sessionID) || entry.checking) return;
    if (entry.started === null) entry.started = now();
    entry.timer = schedule(() => checkpoint(entry), Math.max(1, entry.checkAtMs - elapsed(entry)));
    entry.timer?.unref?.();
  }
  async function checkpoint(entry) {
    if (closed || calls.get(entry.key) !== entry || waiting(entry.sessionID) || entry.checking) return;
    if (elapsed(entry) < entry.checkAtMs) return arm(entry);
    entry.checking = true;
    entry.checks += 1;
    log('checkpoint', entry, { elapsedMs: Math.round(elapsed(entry)), checks: entry.checks });
    try {
      const result = await onCheck({ ...entry, elapsedMs: elapsed(entry) });
      if (closed || calls.get(entry.key) !== entry) return;
      if (result?.terminal) {
        finish(entry.sessionID, entry.callID, result.status || 'terminal-confirmed');
        return;
      }
      // Running, quiet and unknown states all remain monitored. Lack of output
      // is not proof that a long build/import/browser operation has hung.
      log('extended', entry, { reason: result?.status || 'unknown', nextCheckMs: recheckMs });
    } catch (error) {
      log('probe_failed', entry, { error: String(error?.message || error) });
    } finally {
      entry.checking = false;
      if (!closed && calls.get(entry.key) === entry) {
        entry.checkAtMs = elapsed(entry) + recheckMs;
        arm(entry);
      }
    }
  }
  function start({ sessionID, callID, messageID, tool }) {
    if (closed || !sessionID || !callID || !tool || tool === 'question') return;
    const key = keyOf(sessionID, callID);
    if (terminal.has(key)) return;
    let entry = calls.get(key);
    if (!entry) {
      entry = { key, sessionID, callID, messageID, tool, checkAtMs: defaultMs, checks: 0,
        elapsed: 0, started: null, timer: null, checking: false };
      calls.set(key, entry);
      log('started', entry, { firstCheckMs: defaultMs });
    } else {
      entry.messageID ??= messageID;
    }
    // Repeated output updates never postpone the first checkpoint.
    arm(entry);
  }
  function finish(sessionID, callID, status) {
    const key = keyOf(sessionID, callID);
    terminal.add(key);
    if (terminal.size > 4096) terminal.delete(terminal.values().next().value);
    const entry = calls.get(key);
    if (!entry) return;
    stopTimer(entry);
    log('finished', entry, { status, elapsedMs: Math.round(elapsed(entry)) });
    calls.delete(key);
  }
  function wait(sessionID, id, active) {
    if (!sessionID || !id) return;
    let ids = waits.get(sessionID);
    if (!ids) waits.set(sessionID, ids = new Set());
    const wasWaiting = ids.size > 0;
    if (active) ids.add(id); else ids.delete(id);
    if (!ids.size) waits.delete(sessionID);
    if (wasWaiting === (ids.size > 0)) return;
    for (const entry of calls.values()) {
      if (entry.sessionID !== sessionID) continue;
      if (active) pause(entry); else arm(entry);
    }
  }
  function endSession(sessionID) {
    for (const entry of [...calls.values()]) {
      if (entry.sessionID === sessionID) finish(sessionID, entry.callID, 'session-ended');
    }
    waits.delete(sessionID);
  }
  function event(event) {
    if (closed || !event) return;
    const p = event.properties || {};
    if (event.type === 'message.part.updated' && p.part?.type === 'tool') {
      const part = p.part;
      if (['pending', 'running'].includes(part.state?.status)) {
        start({ sessionID: part.sessionID, callID: part.callID, messageID: part.messageID, tool: part.tool });
        const entry = calls.get(keyOf(part.sessionID, part.callID));
        if (entry) entry.partID = part.id;
      } else if (['completed', 'error'].includes(part.state?.status)) {
        finish(part.sessionID, part.callID, part.state.status);
      }
    } else if (['permission.asked', 'permission.updated', 'question.asked'].includes(event.type)) {
      wait(p.sessionID, p.id, true);
    } else if (['permission.replied', 'question.replied', 'question.rejected'].includes(event.type)) {
      wait(p.sessionID, p.requestID || p.permissionID, false);
    } else if (event.type === 'session.idle' || (event.type === 'session.status' && p.status?.type === 'idle')) {
      endSession(p.sessionID);
    } else if (event.type === 'session.deleted') {
      endSession(p.info?.id || p.sessionID);
    } else if (event.type === 'message.part.removed') {
      for (const entry of [...calls.values()]) {
        if (entry.sessionID === p.sessionID && entry.partID === p.partID) finish(entry.sessionID, entry.callID, 'removed');
      }
    }
  }
  function dispose() {
    closed = true;
    for (const entry of calls.values()) stopTimer(entry);
    calls.clear(); waits.clear(); terminal.clear();
  }
  return { start, event, dispose, active: (sessionID, callID) => calls.has(keyOf(sessionID, callID)) };
}
