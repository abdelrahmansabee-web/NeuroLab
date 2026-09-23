// OpenCode Mobile Proxy - Mimics opencode-mobile plugin behavior
const http = require("http");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const OPENCODE_PORT = 4096;
const PROXY_PORT = 4097;
const CLOUDFLARED_PATH = "C:\\Program Files (x86)\\cloudflared\\cloudflared.exe";
const LOG_DIR = "C:\\Users\\acer\\AppData\\Local\\Temp";

let activeTunnel = null;
let cloudflaredProcess = null;

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function log(...args) {
  console.log("[MobileProxy]", ...args);
}

function loadTokens() {
  try {
    const f = path.join(LOG_DIR, "mobile-tokens.json");
    if (fs.existsSync(f)) return JSON.parse(fs.readFileSync(f, "utf8"));
  } catch {}
  return [];
}

function saveTokens(tokens) {
  try {
    fs.writeFileSync(path.join(LOG_DIR, "mobile-tokens.json"), JSON.stringify(tokens, null, 2));
  } catch {}
}

function generateQR(url) {
  return new Promise((resolve, reject) => {
    const qrcode = require("C:\\Users\\acer\\AppData\\Roaming\\npm\\node_modules\\qrcode");
    qrcode.toString(url, { type: "terminal", small: true }, (err, str) => {
      if (err) reject(err);
      else resolve(str);
    });
  });
}

async function startCloudflareTunnel() {
  if (cloudflaredProcess) {
    try { cloudflaredProcess.kill(); } catch {}
    cloudflaredProcess = null;
  }

  const logFile = path.join(LOG_DIR, "cloudflared-proxy.log");
  fs.writeFileSync(logFile, "");

  return new Promise((resolve, reject) => {
    const env = { ...process.env };
    delete env.OPENCODE_SERVER_PASSWORD;
    delete env.OPENCODE_SERVER_USERNAME;

    cloudflaredProcess = spawn(CLOUDFLARED_PATH, ["tunnel", "--url", `http://127.0.0.1:${OPENCODE_PORT}`], {
      windowsHide: true,
      cwd: "C:\\Users\\acer\\AppData\\Local\\Temp",
      env,
    });

    let url = null;
    let timeout = setTimeout(() => {
      if (!url) {
        try { cloudflaredProcess.kill(); } catch {}
        reject(new Error("Tunnel timeout after 60s"));
      }
    }, 60000);

    const checkLine = (line) => {
      if (!line) return;
      fs.appendFileSync(logFile, line + "\n");
      log("cloudflared:", line.trim());
      const match = line.match(/https:\/\/[^\s]+trycloudflare\.com/);
      if (match && !url) {
        url = match[0];
        clearTimeout(timeout);
        activeTunnel = { url, provider: "cloudflare" };
        resolve(activeTunnel);
      }
    };

    cloudflaredProcess.stdout.on("data", (data) => {
      data.toString().split("\n").forEach(checkLine);
    });

    cloudflaredProcess.stderr.on("data", (data) => {
      data.toString().split("\n").forEach(checkLine);
    });

    cloudflaredProcess.on("error", (err) => {
      clearTimeout(timeout);
      reject(err);
    });

    cloudflaredProcess.on("exit", (code) => {
      if (!url) {
        clearTimeout(timeout);
        reject(new Error(`cloudflared exited with code ${code}`));
      }
    });
  });
}

async function handlePushToken(req, res) {
  let body = "";
  req.on("data", (c) => (body += c));
  await new Promise((resolve) => req.on("end", resolve));

  if (req.method === "POST") {
    try {
      const data = JSON.parse(body);
      const { token, platform, deviceId } = data;
      if (!token || !deviceId) {
        res.writeHead(400, { ...cors, "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Missing fields" }));
        return;
      }
      const tokens = loadTokens();
      const idx = tokens.findIndex((t) => t.deviceId === deviceId);
      const newToken = { token, platform: platform || "ios", deviceId, registeredAt: new Date().toISOString() };
      if (idx >= 0) tokens[idx] = newToken;
      else tokens.push(newToken);
      saveTokens(tokens);
      log("Token registered:", deviceId);
      res.writeHead(200, { ...cors, "Content-Type": "application/json" });
      res.end(JSON.stringify({ success: true }));
      return;
    } catch {
      res.writeHead(400, { ...cors, "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Invalid JSON" }));
      return;
    }
  }

  if (req.method === "GET") {
    res.writeHead(200, { ...cors, "Content-Type": "application/json" });
    res.end(JSON.stringify({ count: loadTokens().length }));
    return;
  }

  res.writeHead(404, cors);
  res.end("Not found");
}

async function handleTunnel(req, res) {
  if (req.method === "POST") {
    try {
      log("Starting Cloudflare tunnel...");
      const tunnel = await startCloudflareTunnel();
      log("Tunnel URL:", tunnel.url);
      console.log("\n" + "=".repeat(60));
      console.log("  OpenCode Mobile QR Code");
      console.log("=".repeat(60) + "\n");
      try {
        const qr = await generateQR(tunnel.url);
        console.log(qr);
      } catch (e) {
        console.log("QR generation failed, scan manually or type URL:");
      }
      console.log("\n" + tunnel.url + "\n");
      console.log("=".repeat(60));

      res.writeHead(200, { ...cors, "Content-Type": "application/json" });
      res.end(JSON.stringify({ success: true, type: "cloudflare", url: tunnel.url }));
      return;
    } catch (error) {
      log("Tunnel failed:", error.message);
      res.writeHead(500, { ...cors, "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: error.message }));
      return;
    }
  }

  if (req.method === "GET") {
    res.writeHead(200, { ...cors, "Content-Type": "application/json" });
    res.end(JSON.stringify({ type: activeTunnel ? "cloudflare" : "none", url: activeTunnel?.url || null }));
    return;
  }

  res.writeHead(404, cors);
  res.end("Not found");
}

const server = http.createServer((req, res) => {
  if (req.method === "OPTIONS") {
    res.writeHead(204, cors);
    res.end();
    return;
  }

  if (req.url?.startsWith("/push-token")) {
    handlePushToken(req, res);
    return;
  }

  if (req.url?.startsWith("/tunnel")) {
    handleTunnel(req, res);
    return;
  }

  res.writeHead(404, cors);
  res.end("Not found");
});

server.listen(PROXY_PORT, "0.0.0.0", () => {
  log(`Proxy running on http://0.0.0.0:${PROXY_PORT}`);
  log(`OpenCode server expected on http://localhost:${OPENCODE_PORT}`);
  log("Starting tunnel automatically...");
  handleTunnel({ method: "POST", url: "/tunnel" }, {
    writeHead: () => {},
    end: () => {},
  });
});
