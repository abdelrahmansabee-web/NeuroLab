# Cloudflare + WAF Setup Guide for NeuroLab

This guide explains how to put a Cloudflare proxy in front of the NeuroLab Hugging Face Space so you get DDoS protection, a real Web Application Firewall (WAF), and the original visitor IP forwarded to the backend.

---

## 1. Add a custom domain

HF Spaces can be served from a custom domain.  In your Space settings:

1. Go to **Settings → Domain**.
2. Add your domain (e.g. `neurolab.yourdomain.com`).
3. Copy the CNAME target HF gives you.
4. In your DNS provider, create a CNAME record for `neurolab` pointing to the HF target.

## 2. Proxy through Cloudflare

1. Add the same domain to a Cloudflare account.
2. Create a CNAME record for `neurolab` pointing to the HF target.
3. Set the proxy status to **Proxied** (orange cloud).  This enables Cloudflare's WAF and DDoS protection.
4. In Cloudflare → **SSL/TLS → Overview**, set the mode to **Full (strict)** if HF serves HTTPS, otherwise **Full**.

## 3. Enable Cloudflare WAF

1. Go to **Security → WAF**.
2. Turn on **Managed Rules** (OWASP core ruleset, Cloudflare Managed Ruleset).
3. Add a custom rule to block countries or IP ranges if needed.
4. In **Security → Bots**, enable **Bot Fight Mode** if you want to block automated abuse.

## 4. Forward the real visitor IP

The backend already reads `CF-Connecting-IP` in `security.get_client_ip()`.  Cloudflare sends this header automatically when the proxy is enabled.  No extra configuration is needed as long as the header is not stripped by HF.

To verify, after enabling the proxy, check the application logs for the `waf_block` audit entries; the IP logged should be the visitor's real IP, not Cloudflare's edge IP.

## 5. Restrict access by IP (optional)

If you want to allow only specific IPs or countries, you can:

- Use a Cloudflare Access policy (zero-trust) under **Access → Applications**.
- Or set the environment variable `WAF_BLOCKLIST` on the HF Space to a local file path containing one IP per line (lines starting with `#` are ignored).  The application-level WAF middleware will block those IPs before they reach the endpoints.

## 6. Security headers

The backend already sets HSTS, CSP, X-Content-Type-Options, X-XSS-Protection, and Referrer-Policy.  In Cloudflare, you can add these extra settings:

- **SSL/TLS → Edge Certificates**: Always Use HTTPS = ON, Minimum TLS Version = 1.2, Opportunistic Encryption = ON.
- **Speed → Optimization**: Brotli = ON.
- **Security → Security Level**: set to High or Medium.

## 7. Application-level WAF (fallback)

If you cannot use Cloudflare, the backend includes a lightweight `WAFMiddleware` that:

- Reads `CF-Connecting-IP` (and falls back to `X-Forwarded-For`).
- Enforces a 50 MB request body limit (configurable).
- Blocks common SQLi / XSS / path-traversal patterns in the path and query string.
- Loads an optional IP blocklist from `WAF_BLOCKLIST`.
- Logs blocked requests to `audit.db`.

It runs as a second layer, but it is **not** a substitute for a network WAF.  Use Cloudflare for production traffic.

---

*Last updated for v28.82.*
