import type { WSEvent } from '../types';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

export type EventHandler = (event: WSEvent) => void;
export type ConnectionStateHandler = (state: WSConnectionState) => void;

export type WSConnectionState =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'failed'
  | 'closed';

// ─────────────────────────────────────────────
// SearchWebSocket class
// ─────────────────────────────────────────────

export class SearchWebSocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<EventHandler>>();
  private connectionStateHandlers = new Set<ConnectionStateHandler>();
  private reconnectAttempts = 0;
  private readonly maxReconnects = 10;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isManuallyClosed = false;
  private searchId: string = '';
  private wsUrl: string = '';
  private connectionState: WSConnectionState = 'idle';

  // Message queue for outbound messages during disconnection
  private outboundQueue: string[] = [];
  private readonly maxQueueSize = 50;

  // Last known sequence for reconciliation
  private lastKnownSequence = 0;

  // ─── Public API ───────────────────────────

  connect(searchId: string, wsUrl?: string): void {
    this.searchId = searchId;
    this.isManuallyClosed = false;
    this.reconnectAttempts = 0;

    const base =
      wsUrl ??
      (typeof import.meta !== 'undefined'
        ? (import.meta.env['VITE_WS_BASE_URL'] as string | undefined)
        : undefined) ??
      this.deriveWsBase();

    this.wsUrl = `${base}/ws/search/${searchId}`;
    this.openConnection();
  }

  on(event: string, handler: EventHandler): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }
    this.handlers.get(event)!.add(handler);
  }

  off(event: string, handler: EventHandler): void {
    this.handlers.get(event)?.delete(handler);
  }

  onConnectionStateChange(handler: ConnectionStateHandler): void {
    this.connectionStateHandlers.add(handler);
  }

  offConnectionStateChange(handler: ConnectionStateHandler): void {
    this.connectionStateHandlers.delete(handler);
  }

  send(message: Record<string, unknown>): void {
    const serialized = JSON.stringify(message);
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(serialized);
    } else {
      // Queue for replay on reconnect (bounded)
      if (this.outboundQueue.length < this.maxQueueSize) {
        this.outboundQueue.push(serialized);
      }
    }
  }

  disconnect(): void {
    this.isManuallyClosed = true;
    this.clearReconnectTimer();
    this.ws?.close(1000, 'Client closed');
    this.ws = null;
    this.setConnectionState('closed');
  }

  getConnectionState(): WSConnectionState {
    return this.connectionState;
  }

  getLastKnownSequence(): number {
    return this.lastKnownSequence;
  }

  // ─── Private helpers ──────────────────────

  private deriveWsBase(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}`;
  }

  private openConnection(): void {
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
    }

    this.setConnectionState(this.reconnectAttempts > 0 ? 'reconnecting' : 'connecting');

    try {
      this.ws = new WebSocket(this.wsUrl);
    } catch (err) {
      console.error('[WS] Failed to construct WebSocket:', err);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.setConnectionState('connected');
      this.flushOutboundQueue();
      // Re-subscribe if reconnecting with known sequence
      if (this.lastKnownSequence > 0) {
        this.send({
          type: 'search:subscribe',
          search_id: this.searchId,
          last_known_sequence: this.lastKnownSequence,
        });
      }
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.handleMessage(event);
    };

    this.ws.onerror = () => {
      // onerror always fires before onclose; we handle reconnect in onclose
    };

    this.ws.onclose = (event: CloseEvent) => {
      if (this.isManuallyClosed) return;
      // 1000 = normal closure, 1001 = going away (server shutdown OK)
      if (event.code === 1000 || event.code === 1001) return;
      this.scheduleReconnect();
    };
  }

  private handleMessage(event: MessageEvent): void {
    let parsed: WSEvent;
    try {
      parsed = JSON.parse(event.data as string) as WSEvent;
    } catch {
      console.warn('[WS] Received non-JSON message:', event.data);
      return;
    }

    // Track sequence for reconciliation
    if (parsed.sequence > this.lastKnownSequence) {
      this.lastKnownSequence = parsed.sequence;
    }

    // Dispatch to specific event handlers
    const specific = this.handlers.get(parsed.event);
    specific?.forEach((h) => {
      try {
        h(parsed);
      } catch (err) {
        console.error(`[WS] Handler error for event "${parsed.event}":`, err);
      }
    });

    // Dispatch to wildcard handlers
    const wildcard = this.handlers.get('*');
    wildcard?.forEach((h) => {
      try {
        h(parsed);
      } catch (err) {
        console.error('[WS] Wildcard handler error:', err);
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnects) {
      this.setConnectionState('failed');
      console.warn('[WS] Max reconnection attempts reached. Giving up.');
      return;
    }

    this.reconnectAttempts += 1;
    this.setConnectionState('reconnecting');

    // Exponential backoff with full jitter: random(0, min(1000 * 2^n, 30000))
    const baseDelay = 1_000 * Math.pow(2, this.reconnectAttempts - 1);
    const cappedDelay = Math.min(baseDelay, 30_000);
    const jitteredDelay = Math.random() * cappedDelay;

    console.log(
      `[WS] Reconnecting in ${Math.round(jitteredDelay)}ms (attempt ${this.reconnectAttempts}/${this.maxReconnects})`,
    );

    this.reconnectTimer = setTimeout(() => {
      this.openConnection();
    }, jitteredDelay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private flushOutboundQueue(): void {
    while (this.outboundQueue.length > 0 && this.ws?.readyState === WebSocket.OPEN) {
      const msg = this.outboundQueue.shift();
      if (msg) this.ws.send(msg);
    }
  }

  private setConnectionState(state: WSConnectionState): void {
    if (this.connectionState === state) return;
    this.connectionState = state;
    this.connectionStateHandlers.forEach((h) => {
      try {
        h(state);
      } catch (err) {
        console.error('[WS] Connection state handler error:', err);
      }
    });
  }
}

// ─────────────────────────────────────────────
// Factory function
// ─────────────────────────────────────────────

export const createSearchWebSocket = (
  searchId: string,
  baseUrl?: string,
): SearchWebSocket => {
  const ws = new SearchWebSocket();
  ws.connect(searchId, baseUrl);
  return ws;
};
