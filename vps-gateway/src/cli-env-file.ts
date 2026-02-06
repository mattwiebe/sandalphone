export type EnvMap = Record<string, string>;

const KEY_PATTERN = /^([A-Z0-9_]+)=(.*)$/;

export function parseEnvFile(text: string): EnvMap {
  const out: EnvMap = {};
  const lines = text.split(/\r?\n/);

  for (const line of lines) {
    const match = line.match(KEY_PATTERN);
    if (!match) continue;
    const key = match[1];
    const rawValue = match[2] ?? "";
    out[key] = parseValue(rawValue);
  }

  return out;
}

export function applyEnvUpdates(baseText: string, updates: EnvMap): string {
  const remaining = new Map(Object.entries(updates));
  const lines = baseText.split(/\r?\n/);

  const rewritten = lines.map((line) => {
    const match = line.match(KEY_PATTERN);
    if (!match) return line;

    const key = match[1];
    if (!remaining.has(key)) return line;

    const value = remaining.get(key) ?? "";
    remaining.delete(key);
    return `${key}=${formatValue(value)}`;
  });

  for (const [key, value] of remaining.entries()) {
    rewritten.push(`${key}=${formatValue(value)}`);
  }

  return rewritten.join("\n");
}

export function removeEnvKeys(baseText: string, keys: string[]): string {
  if (keys.length === 0) return baseText;
  const blocked = new Set(keys);
  const lines = baseText.split(/\r?\n/);
  const kept = lines.filter((line) => {
    const match = line.match(KEY_PATTERN);
    if (!match) return true;
    return !blocked.has(match[1]);
  });
  return kept.join("\n");
}

function parseValue(raw: string): string {
  const trimmed = raw.trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function formatValue(value: string): string {
  if (value.length === 0) return "";
  if (/\s|#/.test(value)) {
    return JSON.stringify(value);
  }
  return value;
}
