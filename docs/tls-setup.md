# TLS / HTTPS setup

## Local or test certificates

1. Generate self-signed certificates:
   - `sh scripts/generate-certs.sh`
2. Start the stack with TLS:
   - `docker compose -f docker-compose.yml -f docker-compose.tls.yml up --build`
3. Open `https://localhost`.

The generated files land in `nginx/certs/homeschool-hero.crt` and `nginx/certs/homeschool-hero.key`.

## What the Nginx files do

- `nginx/nginx.conf` proxies plain HTTP to the app and exposes `/.well-known/acme-challenge/`.
- `nginx/nginx-tls.conf` redirects port 80 to 443, terminates TLS, forwards `X-Forwarded-*` headers, and sets HSTS.
- Backend TLS flags (`TLS_ENABLED=true`, `HTTPS_REDIRECT_ENABLED=true`, `SESSION_COOKIE_SECURE=true`) are applied by `docker-compose.tls.yml`.

## Let's Encrypt with certbot

1. Point DNS at the server.
2. Start the TLS compose stack so Nginx serves `/.well-known/acme-challenge/`.
3. Request certificates with certbot using the mounted webroot:
   - `certbot certonly --webroot -w ./data/certbot/www -d example.com -d www.example.com`
4. Mount or copy the issued cert/key to the paths used by `docker-compose.tls.yml`:
   - cert → `nginx/certs/homeschool-hero.crt`
   - key → `nginx/certs/homeschool-hero.key`
5. Restart Nginx after renewal.

### Renewal

- Run `certbot renew`.
- Reload Nginx after a successful renewal so the new files are picked up.

## Reverse proxy behind another web server

If an outer proxy already handles public TLS:

1. Keep that server terminating TLS.
2. Forward traffic to the `nginx` service or directly to the app.
3. Preserve `Host`, `X-Forwarded-Proto`, `X-Forwarded-For`, and `X-Forwarded-Port`.
4. Leave `TLS_ENABLED=true` so backend redirects, secure cookies, and HSTS logic stay aligned.

## Troubleshooting

- **Browser warns about self-signed certs:** expected for local certs; trust the local CA/cert or continue manually.
- **Mixed content:** ensure `VITE_API_URL`, invitation URLs, and any external asset links use `https://`.
- **Renewal succeeds but site still serves old cert:** reload/restart Nginx.
- **Redirect loops:** verify only the public TLS terminator sends `X-Forwarded-Proto=https`.
