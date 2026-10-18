import test from 'node:test';
import assert from 'node:assert/strict';
import { createWatchdog } from './core.mjs';

function fixture() {
  let time = 0, next = 0;
  const timers = new Map(), expired = [], logs = [];
  const guard = createWatchdog({ now: () => time,
    schedule: (fn, delay) => { const id = ++next; timers.set(id, { at: time + delay, fn }); return id; },
    unschedule: (id) => timers.delete(id),
    onCheck: (entry) => { expired.push(entry); return { status: 'running-unverified' }; }, record: (entry) => logs.push(entry),
  });
  async function tick(ms) {
    time += ms;
    for (const [id, timer] of [...timers]) if (timer.at <= time && timers.has(id)) {
      timers.delete(id); timer.fn();
    }
    await Promise.resolve(); await Promise.resolve();
  }
  function part(status, extra = {}) {
    guard.event({ type: 'message.part.updated', properties: { part: {
      id: 'p1', type: 'tool', sessionID: 's1', messageID: 'm1', callID: 'c1', tool: 'bash',
      state: { status, input: { command: 'not logged', timeout: 60000 } }, ...extra,
    } } });
  }
  return { guard, expired, logs, tick, part, timers };
}

test('10-minute deadline ignores the shorter shell timeout', async () => {
  const f = fixture(); f.part('pending'); await f.tick(60000); assert.equal(f.expired.length, 0);
  await f.tick(539999); assert.equal(f.expired.length, 0);
  await f.tick(1); assert.equal(f.expired.length, 1);
  assert.equal(f.expired[0].checkAtMs, 600000);
});
test('repeated output updates and before hook do not reset deadline', async () => {
  const f = fixture(); f.part('pending'); await f.tick(300000);
  f.part('running'); f.guard.start({ sessionID: 's1', callID: 'c1', tool: 'bash', args: { timeout: 1 } });
  await f.tick(300000); assert.equal(f.expired.length, 1);
});
test('completed/error terminal events cancel timer', async () => {
  for (const state of ['completed', 'error']) {
    const f = fixture(); f.part('pending'); f.part(state); await f.tick(900000);
    assert.equal(f.expired.length, 0);
    f.part('running'); await f.tick(900000); assert.equal(f.expired.length, 0);
  }
});
test('permission wait excludes human time and handles multiple requests', async () => {
  const f = fixture(); f.part('running'); await f.tick(300000);
  for (const id of ['a', 'b']) f.guard.event({ type: 'permission.asked', properties: { id, sessionID: 's1' } });
  await f.tick(1200000); assert.equal(f.expired.length, 0);
  f.guard.event({ type: 'permission.replied', properties: { sessionID: 's1', requestID: 'a' } });
  await f.tick(600000); assert.equal(f.expired.length, 0);
  f.guard.event({ type: 'permission.replied', properties: { sessionID: 's1', requestID: 'b' } });
  await f.tick(299999); assert.equal(f.expired.length, 0);
  await f.tick(1); assert.equal(f.expired.length, 1);
});
test('question tool excluded; question events pause other calls', async () => {
  const f = fixture(); f.part('running', { tool: 'question' }); await f.tick(600001);
  assert.equal(f.expired.length, 0);
  f.part('running'); f.guard.event({ type: 'question.asked', properties: { sessionID: 's1', id: 'q1' } });
  await f.tick(900000); assert.equal(f.expired.length, 0);
  f.guard.event({ type: 'question.rejected', properties: { sessionID: 's1', requestID: 'q1' } });
  await f.tick(600000); assert.equal(f.expired.length, 1);
});
test('each call/session is checked independently without cancellation', async () => {
  const f = fixture(); f.part('running');
  f.guard.start({ sessionID: 's1', callID: 'c2', tool: 'read' });
  await f.tick(200000); f.guard.start({ sessionID: 's2', callID: 'c3', tool: 'read' });
  await f.tick(400000); assert.equal(f.expired.length, 2);
  assert.ok(f.guard.active('s1', 'c1'));
  await f.tick(200000); assert.ok(f.expired.some((x) => x.sessionID === 's2'));
  assert.ok(f.guard.active('s2', 'c3'));
});
test('idle/deletion/disposal clean timers', async () => {
  for (const event of [{ type: 'session.status', properties: { sessionID: 's1', status: { type: 'idle' } } },
    { type: 'session.deleted', properties: { info: { id: 's1' } } }]) {
    const f = fixture(); f.part('running'); f.guard.event(event); await f.tick(600000);
    assert.equal(f.expired.length, 0);
  }
  const f = fixture(); f.part('running'); f.guard.dispose(); await f.tick(600000);
  assert.equal(f.expired.length, 0); assert.equal(f.timers.size, 0);
});
test('stuck cleanup is checked every two minutes after initial checkpoint', async () => {
  const f = fixture(); f.part('running');
  await f.tick(600000); assert.equal(f.expired.length, 1);
  await f.tick(119999); assert.equal(f.expired.length, 1);
  await f.tick(1); assert.equal(f.expired.length, 2);
  assert.ok(f.guard.active('s1', 'c1'));
});
test('logs omit command arguments', () => {
  const f = fixture(); f.part('pending'); assert.ok(!JSON.stringify(f.logs).includes('not logged'));
});
test('wait registered before tool starts also pauses timer', async () => {
  const f = fixture(); f.guard.event({ type: 'permission.updated', properties: { id: 'a', sessionID: 's1' } });
  f.part('pending'); await f.tick(700000); assert.equal(f.expired.length, 0);
  f.guard.event({ type: 'permission.replied', properties: { sessionID: 's1', permissionID: 'a' } });
  await f.tick(600000); assert.equal(f.expired.length, 1);
});
test('removed tool part clears deadline', async () => {
  const f = fixture(); f.part('running');
  f.guard.event({ type: 'message.part.removed', properties: { sessionID: 's1', partID: 'p1' } });
  await f.tick(600000); assert.equal(f.expired.length, 0);
});
