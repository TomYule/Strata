import { createHash } from 'node:crypto';

// State and output are evidence, not proof that an OS process is alive.
export function inspectTool(part, previous) {
  if (!part || part.type !== 'tool') return { status: 'unknown', terminal: false };
  const state = part.state || {};
  if (['completed', 'error'].includes(state.status)) return { status: state.status, terminal: true };
  const output = state.output ?? state.metadata?.output ?? '';
  const signature = createHash('sha256').update(JSON.stringify({ status: state.status, output, time: state.time })).digest('hex');
  const changed = previous !== undefined && signature !== previous;
  return { status: changed ? 'progress-observed' : 'running-unverified', terminal: false, signature };
}
