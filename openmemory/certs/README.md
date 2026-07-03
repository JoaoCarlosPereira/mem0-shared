# Certificado TLS da UI (https://memorias.sysmo.com.br)

Coloque aqui (ou em `TLS_CERT_DIR` no `.env`) os dois arquivos:

- `ui.crt` — certificado **fullchain** em PEM (certificado + intermediárias)
- `ui.key` — chave privada em PEM

Emissão recomendada (sem expor nada à internet):

- **Let's Encrypt via desafio DNS-01** (ex.: `certbot certonly --manual
  --preferred-challenges dns -d memorias.sysmo.com.br`) — exige criar um TXT na
  zona DNS; renovação a cada ~90 dias.
- **CA interna da empresa**, se distribuída nos PCs.

Depois de trocar os arquivos, reinicie apenas o proxy:
`docker compose -f docker-compose.scale.yml restart traefik`.
