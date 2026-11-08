# Sobe banco + app e abre o túnel Cloudflare (URL pública aparece no log do cloudflared).
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
cloudflared tunnel --url http://localhost:8000
