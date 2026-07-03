# Certificado TLS da UI (https://memorias.sysmo.com.br)

O Traefik do compose serve a UI em HTTPS usando um certificado montado como
`/certs/ui.crt` (fullchain PEM) e `/certs/ui.key` (chave privada PEM). O
diretório de origem no host é escolhido pela variável **`TLS_CERT_DIR`** (no
`openmemory/.env`); os arquivos dentro dele **precisam** se chamar `ui.crt` e
`ui.key` (o file provider do Traefik não expande variáveis).

## Usando o certificado wildcard da empresa (recomendado)

Já existe um `*.sysmo.com.br` — ele casa com `memorias.sysmo.com.br` por SNI.
No servidor:

```bash
# no openmemory/.env
TLS_CERT_DIR=/home/sysmo-ia/ssl/sysmo.com.br
PROXY_TLS_PORT=443            # este Traefik como edge TLS (requer a 443 livre)

# apontar os nomes canônicos para os arquivos reais do wildcard
cd /home/sysmo-ia/ssl/sysmo.com.br
ln -sf <arquivo-fullchain>.crt ui.crt
ln -sf <arquivo-privkey>.key   ui.key
```

Depois, recriar só o proxy: `docker compose -f docker-compose.scale.yml up -d traefik`.

## Emitir um certificado próprio (alternativa)

Se não usar o wildcard, gere um para `memorias.sysmo.com.br` (Let's Encrypt via
desafio DNS-01, sem expor nada à internet) e coloque como `ui.crt`/`ui.key`
neste diretório (default `TLS_CERT_DIR=openmemory/certs`).

> As duas topologias de TLS estão descritas em `compose/proxy.yml` (ADR-009).
> Se preferir que o proxy da empresa (na 443) termine o TLS e apenas encaminhe
> para `http://IP_DA_LAN:3000`, mantenha `PROXY_TLS_PORT=8443` e ignore este
> certificado.
