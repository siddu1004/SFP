import { LiveChange, LiveResult, LiveState } from './hive';

/** What a LiveSession needs from the editor: how to ask the hive, and where to show the answer. No editor code here. */
export interface LiveHost {
  ask(draft: string, state: LiveState | undefined, change: LiveChange): Promise<LiveResult>;
  show(result: LiveResult): void;
  fail?(error: unknown): void;
}

/**
 * Follows a message as it is typed. `type()` is called on every change of the draft; the hive is asked once typing
 * pauses, an answer for an older draft is thrown away, and the user's pins and removals ride along with each call.
 * Whatever feeds it (a chat input, a text box, a clipboard watcher) is outside this class.
 */
export class LiveSession {
  state: LiveState | undefined;
  last: LiveResult | undefined;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private seq = 0;
  private pending: LiveChange = {};

  constructor(private host: LiveHost, private delayMs = 350) {}

  type(draft: string): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => { this.timer = undefined; void this.run(draft, {}); }, this.delayMs);
  }

  /** The user pinned, removed or restored a skill: ask again straight away with the current draft's state. */
  steer(draft: string, change: LiveChange): Promise<void> {
    if (this.timer) { clearTimeout(this.timer); this.timer = undefined; }
    return this.run(draft, change);
  }

  /** The message was sent: log the decision and start the next message from nothing. */
  async send(draft: string): Promise<LiveResult | undefined> {
    if (this.timer) { clearTimeout(this.timer); this.timer = undefined; }
    await this.run(draft, { commit: true });
    const done = this.last;
    this.state = undefined;
    this.last = undefined;
    this.pending = {};
    return done;
  }

  reset(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
    this.seq++;
    this.state = undefined;
    this.last = undefined;
  }

  private async run(draft: string, change: LiveChange): Promise<void> {
    const mine = ++this.seq;
    try {
      const res = await this.host.ask(draft, this.state, { ...this.pending, ...change });
      if (mine !== this.seq) return;       // a newer draft is already on its way
      this.state = res.state;
      this.last = res;
      this.host.show(res);
    } catch (e) {
      if (mine === this.seq && this.host.fail) this.host.fail(e);
    }
  }
}
