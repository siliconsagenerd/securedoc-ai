import { Readable } from 'node:stream';
import { sendJson } from './http-util.ts';
import { readBody } from './http-util.ts';
import { buildPool, selectNext, softCap, effectiveReserved } from './rotation.ts';
import { dispatchUpstream, parseRetryAfter, resolveModel, sleep, backoff } from './upstream-client.ts';
import type { Config } from './config.ts';
import type { Store } from './db.ts';

const ALIAS = /^upstream-(\d+)$/;

function validateModel(model: unknown, n: number): { pinned: number | null } | { error: string } {
  if (model === undefined || model === 'auto') return { pinned: null };
  if (typeof model !== 'string') return { error: 'model must be a string' };
  const m = ALIAS.exec(model);
  if (!m) return { error: `unknown model alias: ${model}` };
  const idx = Number(m[1]);
  if (idx < 1 || idx > n) return { error: `unknown model alias: ${model}` };
  return { pinned: idx };
}

export async function handleChat(req: any, res: any, config: Config, store: Store): Promise<void> {
  let body: any;
  try {
    const raw = await readBody(req);
    body = JSON.parse(raw.toString('utf8'));
  } catch {
    sendJson(res, 400, { error: { message: 'invalid json body', type: 'invalid_request_error' } });
    return;
  }

  const n = config.upstreams.length;
  const modelCheck = validateModel(body?.model, n);
  if ('error' in modelCheck) {
    sendJson(res, 400, { error: { message: modelCheck.error, type: 'invalid_request_error' } });
    return;
  }
  const requestedModel = typeof body?.model === 'string' ? body.model : undefined;
  const pinned = modelCheck.pinned;
  const stream = body?.stream === true;

  // Reasoning models (e.g. DeepSeek-R1) require every prior assistant turn
  // to echo back its reasoning_content. Many clients/upstreams drop it, which
  // surfaces as "Missing required parameter: messages[x].reasoning_content".
  // Default it to an empty string so the request is never rejected for that
  // reason; preserve any value already supplied (including from other keys).
  // Also disable reasoning effort so upstreams that gate on reasoning_content
  // never require it to be sent back (fixes multi-turn sessions).
  if (Array.isArray(body?.messages)) {
    for (const m of body.messages) {
      if (!m || typeof m !== 'object' || m.role !== 'assistant') continue;
      if (m.reasoning_content === undefined || m.reasoning_content === null) {
        m.reasoning_content = typeof m.reasoning === 'string' ? m.reasoning : '';
      }
      // Also strip any stray reasoning fields that might confuse upstreams
      if (m.reasoning === undefined) m.reasoning = m.reasoning_content;
    }
  }
  // Force reasoning off for every request so upstreams that require
  // reasoning_content on prior assistant turns never reject the call.
  body.reasoning_effort = 'none';
  body.thinking = { type: 'disabled' };
  const deadline = Date.now() + config.totalDeadlineMs;
  const tried = new Set<number>();
  const maxAttempts = pinned !== null ? 1 : config.maxAttempts;
  const softCapValue = softCap(config.dailyLimit, config.rotateAtFraction);

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (Date.now() > deadline) break;
    const now = Date.now();
    const pool = buildPool(config, store.getStates(), now);

    let index: number | null;
    if (pinned !== null) {
      const entry = pool[pinned - 1];
      if (!entry || !entry.configured || entry.disabled || entry.cooldownUntilMs > now || tried.has(pinned)) {
        sendJson(res, 503, { error: { message: 'pinned upstream unavailable', type: 'upstream_unavailable' } });
        return;
      }
      index = pinned;
    } else {
      index = selectNext(pool, store.getCurrentIndex(), softCapValue, now, tried);
    }
    if (index === null) break;

    tried.add(index);
    const upstream = config.upstreams[index - 1];

    const reserve = store.reserve(upstream.name, config.windowMs, softCapValue);
    if (!reserve.ok) continue;
    store.setCurrentIndex(index);

    const model = resolveModel(requestedModel, upstream);
    const started = Date.now();
    let result;
    try {
      result = await dispatchUpstream({ upstream, model, body, timeoutMs: config.perAttemptTimeoutMs });
    } catch {
      store.markCooldown(upstream.name, Date.now() + config.cooldownMs, 0);
      store.recordDispatch(upstream.name, 'network-error', 0, Date.now() - started);
      await sleep(backoff(config, attempt));
      continue;
    }

    if (result.kind === 'ok') {
      store.recordDispatch(upstream.name, 'ok', result.status, Date.now() - started);
      if (stream) {
        res.writeHead(200, {
          'content-type': 'text/event-stream',
          'cache-control': 'no-cache',
          connection: 'keep-alive',
        });
        const readable = Readable.fromWeb(result.stream as any);
        req.on('close', () => readable.destroy());
        readable.pipe(res);
        return;
      }
      const text = await new Response(result.stream as any).text();
      res.writeHead(200, { 'content-type': result.headers.get('content-type') ?? 'application/json' });
      res.end(text);
      return;
    }

    if (result.kind === 'rate-limited') {
      const ra = parseRetryAfter(result.headers.get('retry-after'));
      store.markCooldown(upstream.name, Date.now() + (ra ?? config.cooldownMs), result.status);
      store.recordDispatch(upstream.name, 'rate-limited', result.status, Date.now() - started);
      await sleep(backoff(config, attempt));
      continue;
    }

    if (result.kind === 'server-error') {
      store.markCooldown(upstream.name, Date.now() + config.cooldownMs, result.status);
      store.recordDispatch(upstream.name, 'server-error', result.status, Date.now() - started);
      await sleep(backoff(config, attempt));
      continue;
    }

    if (result.kind === 'auth') {
      store.markDisabled(upstream.name, `auth ${result.status}`, result.status);
      store.recordDispatch(upstream.name, 'auth', result.status, Date.now() - started);
      continue;
    }

    store.recordDispatch(upstream.name, 'client-error', result.status, Date.now() - started);
    res.writeHead(result.status, { 'content-type': result.headers.get('content-type') ?? 'application/json' });
    res.end(result.text ?? '');
    return;
  }

  if (!res.headersSent) {
    sendJson(res, 502, { error: { message: 'all upstreams failed', type: 'upstream_failed' } });
  }
}

export function handleModels(res: any, config: Config): void {
  const data = [{ id: 'auto', object: 'model', owned_by: 'api-rotation-service' }];
  for (let i = 1; i <= config.upstreams.length; i++) {
    data.push({
      id: `upstream-${String(i).padStart(2, '0')}`,
      object: 'model',
      owned_by: 'api-rotation-service',
    });
  }
  sendJson(res, 200, { object: 'list', data });
}

const RECENT_EVENTS_LIMIT = 10;

export function buildStatus(config: Config, store: Store): any {
  const now = Date.now();
  const byName = new Map(store.getStates().map((s) => [s.name, s]));
  const counts = store.outcomeCounts();
  const threshold = softCap(config.dailyLimit, config.rotateAtFraction);
  let successTotal = 0;
  let failureTotal = 0;
  const upstreams = config.upstreams.map((u) => {
    const s = byName.get(u.name);
    const reserved = s ? effectiveReserved(s, now, config.windowMs) : 0;
    const inCooldown = !!s && s.cooldownUntilMs > now;
    const disabled = !!s?.disabled;
    const c = counts.get(u.name) ?? { success: 0, failure: 0 };
    successTotal += c.success;
    failureTotal += c.failure;
    return {
      name: u.name,
      index: u.index,
      configured: u.configured,
      enabled: u.configured && !disabled,
      disabled,
      disabledReason: disabled ? (s?.disabledReason ?? null) : null,
      health: disabled ? 'disabled' : !u.configured ? 'unconfigured' : inCooldown ? 'cooldown' : 'ready',
      inCooldown,
      cooldownUntilMs: s?.cooldownUntilMs ?? 0,
      model: u.configured ? u.model : null,
      used: reserved,
      limit: config.dailyLimit,
      threshold,
      successCount: c.success,
      failureCount: c.failure,
      lastStatus: s?.lastStatus ?? null,
    };
  });
  const ready = upstreams.some((u) => u.enabled && !u.inCooldown && u.used < threshold);
  const currentIndex = store.getCurrentIndex();
  const active = config.upstreams[currentIndex - 1] ?? null;
  return {
    nowMs: now,
    ready,
    currentIndex,
    currentUpstream: active ? active.name : null,
    windowMs: config.windowMs,
    dailyLimit: config.dailyLimit,
    rotateAtFraction: config.rotateAtFraction,
    threshold,
    totals: { success: successTotal, failure: failureTotal },
    events: store.recentEvents(RECENT_EVENTS_LIMIT),
    upstreams,
  };
}
