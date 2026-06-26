import { app, safeStorage } from 'electron';
import fs from 'node:fs/promises';
import path from 'node:path';

export interface SecretStore {
  set(key: string, value: string): Promise<void>;
  get(key: string): Promise<string | null>;
  clear(key: string): Promise<void>;
  isHardwareBacked(): Promise<boolean>;
}

const memoryStore = new Map<string, string>();
const storePath = path.join(app.getPath('userData'), 'secrets.enc.json');

async function readDiskStore(): Promise<Record<string, string>> {
  try {
    const raw = await fs.readFile(storePath, 'utf8');
    return JSON.parse(raw) as Record<string, string>;
  } catch {
    return {};
  }
}

async function writeDiskStore(data: Record<string, string>): Promise<void> {
  await fs.mkdir(path.dirname(storePath), { recursive: true });
  await fs.writeFile(storePath, JSON.stringify(data), { encoding: 'utf8', mode: 0o600 });
}

async function canPersistEncryptedSecrets(): Promise<boolean> {
  try {
    if (safeStorage.getSelectedStorageBackend?.() === 'basic_text') {
      return false;
    }
    return await safeStorage.isAsyncEncryptionAvailable();
  } catch {
    return false;
  }
}

export const secretStore: SecretStore = {
  async set(key, value) {
    if (!(await canPersistEncryptedSecrets())) {
      memoryStore.set(key, value);
      return;
    }

    const encrypted = await safeStorage.encryptStringAsync(value);
    const data = await readDiskStore();
    data[key] = encrypted.toString('base64');
    await writeDiskStore(data);
  },

  async get(key) {
    if (!(await canPersistEncryptedSecrets())) {
      return memoryStore.get(key) ?? null;
    }

    const data = await readDiskStore();
    const encoded = data[key];
    if (!encoded) return null;

    try {
      const decrypted = await safeStorage.decryptStringAsync(Buffer.from(encoded, 'base64'));
      if (decrypted.shouldReEncrypt) {
        await this.set(key, decrypted.result);
      }
      return decrypted.result;
    } catch {
      await this.clear(key);
      return null;
    }
  },

  async clear(key) {
    memoryStore.delete(key);
    const data = await readDiskStore();
    if (key in data) {
      delete data[key];
      await writeDiskStore(data);
    }
  },

  async isHardwareBacked() {
    return canPersistEncryptedSecrets();
  },
};
