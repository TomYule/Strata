import test from 'node:test';
import assert from 'node:assert/strict';
import { inspectTool } from './probe.mjs';
import { createWatchdog } from './core.mjs';

test('terminal persisted state stops monitoring', () => {
  assert.deepEqual(inspectTool({ type: 'tool', state: { status: 'completed' } }), { status: 'completed', terminal: true });
  assert.equal(inspectTool({ type: 'tool', state: { status: 'error' } }).terminal, true);
});
test('running alone or unchanged output is not proof of live progress', () => {
  const part = { type: 'tool', state: { status: 'running', metadata: { output: 'hello' } } };
  const first = inspectTool(part);
  assert.equal(first.status, 'running-unverified');
  assert.equal(inspectTool(part, first.signature).status, 'running-unverified');
  part.state.metadata.output += ' world';
  assert.equal(inspectTool(part, first.signature).status, 'progress-observed');
});
test('missing record remains unknown rather than being killed', () => {
  assert.deepEqual(inspectTool(undefined), { status: 'unknown', terminal: false });
});
test('probe confirms terminal state after missed completion event', async () => {
  let callback; let time = 0;
  const guard = createWatchdog({ now: () => time, schedule: (f) => { callback = f; return 1; }, unschedule: () => {},
    onCheck: async () => ({ terminal: true, status: 'completed' }) });
  guard.start({ sessionID: 's', callID: 'c', tool: 'bash' });
  time = 600000; await callback(); assert.equal(guard.active('s', 'c'), false); guard.dispose();
});
test('failed probe extends and does not create overlapping checks', async () => {
  let callback; let time = 0; let checks = 0;
  const guard = createWatchdog({ now: () => time, schedule: (f) => { callback = f; return 1; }, unschedule: () => {},
    onCheck: async () => { checks++; throw new Error('status offline'); } });
  guard.start({ sessionID: 's', callID: 'c', tool: 'bash' });
  time = 600000; await callback(); assert.equal(checks, 1); assert.equal(guard.active('s', 'c'), true);
  time += 120000; await callback(); assert.equal(checks, 2); guard.dispose();
});
