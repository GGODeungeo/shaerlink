/** Deterministic per-day shuffle: same order all day (calm to browse,
 * matches the "매일 아침 10시 업데이트" framing), different order once the
 * date rolls over. `salt` lets independent shelves (e.g. per category) get
 * uncorrelated orders instead of all reshuffling in lockstep. */
export function dailyShuffle<T>(items: T[], salt: string): T[] {
  const rng = mulberry32(hashSeed(todayKey() + salt));
  const shuffled = [...items];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function hashSeed(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return h;
}

function mulberry32(seed: number): () => number {
  let state = seed | 0;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
