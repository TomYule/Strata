import { appendFileSync, mkdirSync, statSync, renameSync, existsSync, unlinkSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { createWatchdog } from './core.mjs';
import { inspectTool } from './probe.mjs';

const FIRST_CHECK_MS = 600000;
const RECHECK_MS = 120000;
const CONTROL_TIMEOUT_MS = 5000;

export default async function toolWatchdog({ client, directory }) {
  const logDir = join(homedir(), '.local', 'state', 'opencode');
  const logPath = join(logDir, 'tool-watchdog.jsonl');
  const signatures = new Map();
  function record(entry) {
    try {
      mkdirSync(logDir, { recursive: true });
      if (existsSync(logPath) && statSync(logPath).size > 2 * 1024 * 1024) {
        if (existsSync(logPath + '.1')) unlinkSync(logPath + '.1');
        renameSync(logPath, logPath + '.1');
      }
      // No arguments, prompts, output or credentials are logged.
      appendFileSync(logPath, JSON.stringify({ time: new Date().toISOString(), directory, ...entry }) + '\n');
      if (entry.kind === 'finished') signatures.delete(`${entry.sessionID}:${entry.callID}`);
    } catch (error) {
      console.error(`[tool-watchdog] Cannot write diagnostic log: ${error.message}`);
    }
  }
  async function bounded(operation) {
    const controller = new AbortController();
    let timer;
    try {
      const result = await Promise.race([
        Promise.resolve().then(() => operation(controller.signal)),
        new Promise((_, reject) => {
          timer = setTimeout(() => {
            controller.abort();
            reject(new Error('OpenCode status request exceeded 5 seconds'));
          }, CONTROL_TIMEOUT_MS);
          timer.unref?.();
        }),
      ]);
      if (result?.error) throw new Error('OpenCode status API returned an error');
      return result;
    } finally {
      clearTimeout(timer);
    }
  }
  async function notify(message) {
    try {
      await bounded((signal) => client.tui.showToast({
        query: { directory }, body: { title: 'Tool watchdog', message, variant: 'warning', duration: 15000 }, signal,
      }));
    } catch (error) {
      record({ kind: 'notification_failed', error: error.message });
      console.error(`[tool-watchdog] ${message}`);
    }
  }
  const watchdog = createWatchdog({
    defaultMs: FIRST_CHECK_MS,
    recheckMs: RECHECK_MS,
    record,
    onCheck: async (entry) => {
      try {
        // Query only this message, never the whole conversation or unrelated sessions.
        let data;
        if (entry.messageID) {
          const response = await bounded((signal) => client.session.message({
            path: { id: entry.sessionID, messageID: entry.messageID }, query: { directory }, signal,
          }));
          data = response?.data;
        }
        const part = data?.parts?.find((p) => p.type === 'tool' && p.callID === entry.callID);
        const result = inspectTool(part, signatures.get(entry.key));
        if (result.signature) signatures.set(entry.key, result.signature);
        if (result.terminal) return result;
        const statuses = await bounded((signal) => client.session.status({ query: { directory }, signal }));
        const sessionStatus = statuses?.data?.[entry.sessionID]?.type || 'unknown';
        if (sessionStatus === 'idle') return { terminal: true, status: 'session-idle-confirmed' };
        record({ kind: 'status_checked', sessionID: entry.sessionID, callID: entry.callID,
          tool: entry.tool, status: result.status, sessionStatus });
        // At 10 minutes, then every 10 further minutes: do not flood the UI.
        if (entry.checks === 1 || (entry.checks - 1) % 5 === 0) {
          const detail = result.status === 'progress-observed' ? 'Output/state progressed.' : 'Process progress is not confirmed; running alone is not proof.';
          void notify(`${entry.tool}: ${Math.floor(entry.elapsedMs / 60000)} min elapsed. ${detail} Waiting 2 more minutes; Esc remains available. No automatic retry or kill.`);
        }
        return result;
      } catch (error) {
        record({ kind: 'probe_failed', sessionID: entry.sessionID, callID: entry.callID,
          tool: entry.tool, error: error.message });
        if (entry.checks === 1 || (entry.checks - 1) % 5 === 0) {
          void notify('Tool status could not be verified. Keeping the call alive and checking again in 2 minutes. Use Esc if needed.');
        }
        return { status: 'unknown', terminal: false };
      }
    },
  });
  record({ kind: 'loaded', firstCheckMs: FIRST_CHECK_MS, recheckMs: RECHECK_MS, policy: 'check-and-extend' });
  return {
    event: async ({ event }) => { watchdog.event(event); },
    'tool.execute.before': async (input) => { watchdog.start(input); },
    // Do not clear at tool.execute.after: result persistence/other hooks may still hang.
    dispose: async () => { watchdog.dispose(); signatures.clear(); record({ kind: 'disposed' }); },
  };
}
