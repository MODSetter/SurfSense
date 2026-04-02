const MAX_BUFFER_LENGTH = 4000;
const KEYCODE_TO_CHAR: Record<number, [string, string]> = {};

let keystrokeBuffer = '';
let lastTrackedApp = '';

export function buildKeycodeMap(): void {
  const letters: [string, number][] = [
    ['q', 16], ['w', 17], ['e', 18], ['r', 19], ['t', 20],
    ['y', 21], ['u', 22], ['i', 23], ['o', 24], ['p', 25],
    ['a', 30], ['s', 31], ['d', 32], ['f', 33], ['g', 34],
    ['h', 35], ['j', 36], ['k', 37], ['l', 38],
    ['z', 44], ['x', 45], ['c', 46], ['v', 47],
    ['b', 48], ['n', 49], ['m', 50],
  ];
  for (const [ch, code] of letters) {
    KEYCODE_TO_CHAR[code] = [ch, ch.toUpperCase()];
  }

  const digits: [string, string, number][] = [
    ['1', '!', 2], ['2', '@', 3], ['3', '#', 4], ['4', '$', 5],
    ['5', '%', 6], ['6', '^', 7], ['7', '&', 8], ['8', '*', 9],
    ['9', '(', 10], ['0', ')', 11],
  ];
  for (const [norm, shifted, code] of digits) {
    KEYCODE_TO_CHAR[code] = [norm, shifted];
  }

  const punctuation: [string, string, number][] = [
    [';', ':', 39], ['=', '+', 13], [',', '<', 51], ['-', '_', 12],
    ['.', '>', 52], ['/', '?', 53], ['`', '~', 41], ['[', '{', 26],
    ['\\', '|', 43], [']', '}', 27], ["'", '"', 40],
  ];
  for (const [norm, shifted, code] of punctuation) {
    KEYCODE_TO_CHAR[code] = [norm, shifted];
  }
}

export function resetBuffer(): void {
  keystrokeBuffer = '';
}

export function appendToBuffer(char: string): void {
  keystrokeBuffer += char;
  if (keystrokeBuffer.length > MAX_BUFFER_LENGTH) {
    keystrokeBuffer = keystrokeBuffer.slice(-MAX_BUFFER_LENGTH);
  }
}

export function removeLastChar(): void {
  if (keystrokeBuffer.length > 0) {
    keystrokeBuffer = keystrokeBuffer.slice(0, -1);
  }
}

export function getBuffer(): string {
  return keystrokeBuffer;
}

export function getBufferTrimmed(): string {
  return keystrokeBuffer.trim();
}

export function getLastTrackedApp(): string {
  return lastTrackedApp;
}

export function setLastTrackedApp(app: string): void {
  lastTrackedApp = app;
}

export function resolveChar(keycode: number, shift: boolean): string | null {
  const mapping = KEYCODE_TO_CHAR[keycode];
  if (!mapping) return null;
  return shift ? mapping[1] : mapping[0];
}
