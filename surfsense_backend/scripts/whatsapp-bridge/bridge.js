#!/usr/bin/env node

import {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeWASocket,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import express from "express";
import { mkdirSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";
import pino from "pino";
import qrcode from "qrcode-terminal";

const PORT = Number(process.env.PORT || "9929");
const SESSION_DIR = process.env.WHATSAPP_SESSION_DIR || "/data/sessions";
const SEND_TIMEOUT_MS = Number(process.env.WHATSAPP_SEND_TIMEOUT_MS || "60000");
const PAIRING_TIMEOUT_MS = Number(process.env.WHATSAPP_PAIRING_TIMEOUT_MS || "30000");
const MAX_QUEUE_SIZE = Number(process.env.WHATSAPP_MAX_QUEUE_SIZE || "100");
const WHATSAPP_MODE = process.env.WHATSAPP_MODE || "self-chat";
const SENT_ECHO_TTL_MS = 60_000;

mkdirSync(SESSION_DIR, { recursive: true });

const app = express();
app.use(express.json({ limit: "2mb" }));

const logger = pino({ level: process.env.WHATSAPP_DEBUG ? "debug" : "warn" });
const messageQueue = [];
const sentKeys = new Map();
const recentlySentIds = new Set();

let sock = null;
let connectionState = "disconnected";
let latestQr = null;
let starting = null;
let pendingPairing = null;

function resetSessionState() {
  sock = null;
  latestQr = null;
  sentKeys.clear();
  recentlySentIds.clear();
  mkdirSync(SESSION_DIR, { recursive: true });
  for (const entry of readdirSync(SESSION_DIR)) {
    rmSync(path.join(SESSION_DIR, entry), { recursive: true, force: true });
  }
}

function resolvePendingPairing(payload) {
  if (!pendingPairing) return;
  clearTimeout(pendingPairing.timer);
  pendingPairing.resolve(payload);
  pendingPairing = null;
}

function rejectPendingPairing(error) {
  if (!pendingPairing) return;
  clearTimeout(pendingPairing.timer);
  pendingPairing.reject(error);
  pendingPairing = null;
}

async function maybeRequestPairingCode(update = {}) {
  if (!pendingPairing || pendingPairing.inFlight || !sock) return;

  const canRequestPairingCode =
    update.connection === "connecting" ||
    Boolean(update.qr) ||
    Boolean(latestQr);

  if (!canRequestPairingCode) return;

  pendingPairing.inFlight = true;
  connectionState = "pairing";
  try {
    const code = await sock.requestPairingCode(pendingPairing.phoneNumber);
    resolvePendingPairing({ status: "pairing", pairing_code: code, expires_in: 60 });
  } catch (error) {
    rejectPendingPairing(error);
  }
}

function requestPairingCodeWhenReady(phoneNumber) {
  if (connectionState === "connected") {
    return Promise.resolve({ status: "connected", pairing_code: null, expires_in: 0 });
  }

  if (pendingPairing) {
    return Promise.reject(new Error("A WhatsApp pairing request is already in progress"));
  }

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pendingPairing = null;
      reject(new Error("Timed out waiting for WhatsApp to become ready for pairing"));
    }, PAIRING_TIMEOUT_MS);

    pendingPairing = {
      phoneNumber,
      resolve,
      reject,
      timer,
      inFlight: false,
    };

    void startSocket()
      .then(() => maybeRequestPairingCode())
      .catch((error) => rejectPendingPairing(error));
    void maybeRequestPairingCode();
  });
}

function normalizeText(message) {
  const content = message?.message || {};
  return (
    content.conversation ||
    content.extendedTextMessage?.text ||
    content.imageMessage?.caption ||
    content.videoMessage?.caption ||
    content.documentMessage?.caption ||
    ""
  );
}

function enqueueMessage(message) {
  const remoteJid = message?.key?.remoteJid;
  const id = message?.key?.id;
  if (!remoteJid || !id || !message?.message) return;
  if (messageQueue.length >= MAX_QUEUE_SIZE) messageQueue.shift();
  messageQueue.push({
    event: "messages.upsert",
    key: message.key,
    chatId: remoteJid,
    senderId: message.key.participant || remoteJid,
    messageId: id,
    fromMe: Boolean(message.key.fromMe),
    isGroup: remoteJid.endsWith("@g.us"),
    body: normalizeText(message),
    timestamp: Number(message.messageTimestamp || Date.now() / 1000),
    raw: message,
  });
}

function rememberSentMessage(sent) {
  const sentId = sent?.key?.id;
  if (!sentId) return;
  sentKeys.set(sentId, sent.key);
  recentlySentIds.add(sentId);
  setTimeout(() => {
    recentlySentIds.delete(sentId);
  }, SENT_ECHO_TTL_MS).unref?.();
}

function withTimeout(promise, timeoutMs) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`sendMessage timed out after ${timeoutMs}ms`)),
      timeoutMs,
    );
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

async function startSocket() {
  if (starting) return starting;
  starting = (async () => {
    connectionState = "connecting";
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
    const { version } = await fetchLatestBaileysVersion();
    sock = makeWASocket({
      version,
      auth: state,
      logger,
      printQRInTerminal: false,
      browser: ["SurfSense", "Chrome", "120.0"],
      syncFullHistory: false,
      markOnlineOnConnect: false,
      getMessage: async () => ({ conversation: "" }),
    });

    sock.ev.on("creds.update", saveCreds);
    sock.ev.on("connection.update", (update) => {
      const { connection, lastDisconnect, qr } = update;
      if (qr) {
        latestQr = qr;
        connectionState = "qr";
        qrcode.generate(qr, { small: true });
        void maybeRequestPairingCode(update);
      }
      if (connection === "open") {
        latestQr = null;
        connectionState = "connected";
        console.log("WhatsApp connected");
        resolvePendingPairing({ status: "connected", pairing_code: null, expires_in: 0 });
      }
      if (connection === "close") {
        const reason = new Boom(lastDisconnect?.error)?.output?.statusCode;
        connectionState = "disconnected";
        if (reason === DisconnectReason.loggedOut) {
          console.error("WhatsApp logged out; clearing session and waiting for pairing.");
          connectionState = "logged_out";
          resetSessionState();
          setTimeout(() => {
            starting = null;
            void startSocket();
          }, 1000);
          return;
        }
        setTimeout(() => {
          starting = null;
          void startSocket();
        }, reason === 515 ? 1000 : 3000);
      }
      void maybeRequestPairingCode(update);
    });

    sock.ev.on("messages.upsert", ({ messages, type }) => {
      if (type !== "notify" && type !== "append") return;
      for (const message of messages || []) {
        const chatId = message?.key?.remoteJid;
        if (!chatId) continue;
        if (chatId.endsWith("@g.us") || chatId.includes("status@broadcast")) continue;

        if (message?.key?.fromMe) {
          if (WHATSAPP_MODE !== "self-chat") continue;
          if (recentlySentIds.has(message.key.id)) continue;

          const myNumber = (sock.user?.id || "").replace(/:.*@/, "@").replace(/@.*/, "");
          const myLid = (sock.user?.lid || "").replace(/:.*@/, "@").replace(/@.*/, "");
          const chatNumber = chatId.replace(/@.*/, "");
          const isSelfChat =
            (myNumber && chatNumber === myNumber) || (myLid && chatNumber === myLid);
          if (!isSelfChat) continue;
        } else if (WHATSAPP_MODE === "self-chat") {
          continue;
        }

        enqueueMessage(message);
      }
    });
  })();
  try {
    await starting;
  } finally {
    starting = null;
  }
}

app.get("/health", (_req, res) => {
  res.json({
    status: connectionState,
    hasQr: Boolean(latestQr),
    qr: latestQr,
    queueDepth: messageQueue.length,
    user: sock?.user || null,
  });
});

app.get("/messages", (_req, res) => {
  const messages = messageQueue.splice(0, messageQueue.length);
  res.json(messages);
});

app.post("/send", async (req, res) => {
  try {
    if (!sock || connectionState !== "connected") {
      return res.status(503).json({ error: "WhatsApp is not connected" });
    }
    const { chatId, message, replyTo } = req.body || {};
    if (!chatId || !message) {
      return res.status(400).json({ error: "chatId and message are required" });
    }
    const payload = { text: String(message) };
    if (replyTo) {
      payload.contextInfo = { stanzaId: String(replyTo) };
    }
    const sent = await withTimeout(sock.sendMessage(chatId, payload), SEND_TIMEOUT_MS);
    rememberSentMessage(sent);
    res.json({ messageId: sent?.key?.id || null, raw: sent });
  } catch (error) {
    res.status(500).json({ error: error?.message || "send failed" });
  }
});

app.post("/edit", async (req, res) => {
  try {
    if (!sock || connectionState !== "connected") {
      return res.status(503).json({ error: "WhatsApp is not connected" });
    }
    const { chatId, messageId, message } = req.body || {};
    if (!chatId || !messageId || !message) {
      return res.status(400).json({ error: "chatId, messageId and message are required" });
    }
    const key = sentKeys.get(String(messageId)) || {
      remoteJid: chatId,
      id: String(messageId),
      fromMe: true,
    };
    const sent = await withTimeout(
      sock.sendMessage(chatId, { text: String(message), edit: key }),
      SEND_TIMEOUT_MS,
    );
    rememberSentMessage(sent);
    res.json({ messageId: sent?.key?.id || messageId, raw: sent });
  } catch (error) {
    res.status(500).json({ error: error?.message || "edit failed" });
  }
});

app.post("/typing", async (req, res) => {
  try {
    if (!sock || connectionState !== "connected") return res.status(204).end();
    const { chatId } = req.body || {};
    if (chatId) {
      await sock.sendPresenceUpdate("composing", chatId);
    }
    res.status(204).end();
  } catch {
    res.status(204).end();
  }
});

app.post("/pair", async (req, res) => {
  try {
    const phoneNumber = String(req.body?.phoneNumber || req.body?.phone_number || "").replace(/\D/g, "");
    if (!phoneNumber) {
      return res.status(400).json({ error: "phoneNumber is required for pairing code" });
    }
    res.json(await requestPairingCodeWhenReady(phoneNumber));
  } catch (error) {
    res.status(500).json({ error: error?.message || "pairing failed" });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(
    `SurfSense WhatsApp bridge listening on ${PORT}; session=${path.resolve(SESSION_DIR)}; mode=${WHATSAPP_MODE}`,
  );
  void startSocket();
});
