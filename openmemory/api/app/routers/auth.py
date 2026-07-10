"""Autenticação de pessoas via Google (feature auth Google, ADR-002/ADR-004).

Fluxo: a UI (NextAuth) obtém o ID token do Google e o envia em
``POST /api/v1/auth/google``. O backend valida o token (assinatura, ``aud``,
``iss``, ``exp``) e o domínio corporativo (claim ``hd`` ==
``AUTH_ALLOWED_DOMAIN``), faz upsert do usuário ``person`` (chave = claim
``sub``, estável — o e-mail é apenas informativo) e emite o JWT de sessão
próprio (``app.utils.session_jwt``).
"""

import os
import uuid
from typing import Optional

from app.database import get_db
from app.models import (
    USER_TYPE_LEGACY_HOST,
    USER_TYPE_PERSON,
    LinkAuditLog,
    Machine,
    MachineStatus,
    User,
    get_current_utc_time,
)
from app.utils.groups import get_or_create_group, group_of_hostname, normalize_group_name
from app.utils.hostname_validation import require_sysmo_hostname
from app.utils.machine_resolver import (
    backfill_legacy_user_id,
    canonical_machine_hostname,
    resolve_or_create_machine,
)
from app.utils.identity import resolve_hostname
from app.utils.identity_links import invalidate_identity_link_cache
from app.utils.logging_context import auth_method_var
from app.utils.session_jwt import (
    SessionJwtError,
    decode_session_jwt,
    issue_session_jwt,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _allowed_audiences() -> set:
    """Client IDs aceitos como ``aud`` do ID token.

    Dois fluxos coexistem (ADR-002 redirect + ADR-007 device flow) e cada um
    pode ter seu próprio client OAuth no Google Cloud: ``GOOGLE_CLIENT_ID``
    (Aplicativo da Web) e ``GOOGLE_DEVICE_CLIENT_ID`` (TVs/entrada limitada).
    """
    return {
        cid
        for cid in (
            os.getenv("GOOGLE_CLIENT_ID", "").strip(),
            os.getenv("GOOGLE_DEVICE_CLIENT_ID", "").strip(),
        )
        if cid
    }


def _verify_google_id_token(raw_token: str) -> dict:
    """Valida o ID token junto ao Google e devolve os claims.

    Isolada em função de módulo para ser substituível nos testes (monkeypatch)
    sem depender de rede. Assinatura/``iss``/``exp`` são validados pela lib;
    o ``aud`` é conferido manualmente contra os client IDs configurados
    (redirect e device flow podem usar clients distintos).
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    claims = google_id_token.verify_oauth2_token(
        raw_token, google_requests.Request(), audience=None
    )
    allowed = _allowed_audiences()
    if allowed and str(claims.get("aud") or "") not in allowed:
        raise ValueError("aud do ID token não corresponde aos clients configurados")
    return claims


class GoogleLoginRequest(BaseModel):
    id_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    user_type: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    first_login: bool
    user: UserOut


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hostname: str
    status: MachineStatus
    linked_at: Optional[object] = None


class MeResponse(BaseModel):
    user: UserOut
    machine: Optional[MachineOut] = None
    group: Optional[str] = None


def _allowed_domain() -> str:
    return os.getenv("AUTH_ALLOWED_DOMAIN", "").strip().lower()


def _linked_machine(db: Session, user: User) -> Optional[Machine]:
    return (
        db.query(Machine)
        .filter(Machine.linked_user_id == user.id)
        .order_by(Machine.linked_at.desc())
        .first()
    )


def _effective_group_name(
    db: Session, user: User, machine: Optional[Machine]
) -> Optional[str]:
    """Grupo efetivo da conta — alinhado ao que o MCP usa (hostname legado).

    A pessoa (Google) e o usuário legado (hostname) podem divergir quando o MCP
    já vinculou o grupo na instalação e o onboarding gravou Default por engano.
    """
    if machine is not None:
        legacy_group = group_of_hostname(machine.hostname)
        if legacy_group:
            return legacy_group
    if user.group is not None:
        return user.group.name
    return None


def get_current_person(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve a pessoa autenticada a partir do Bearer (JWT de sessão)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="credencial ausente")
    try:
        claims = decode_session_jwt(authorization[7:].strip())
        user_pk = uuid.UUID(claims["sub"])
    except (SessionJwtError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="sessão inválida ou expirada")
    user = db.query(User).filter(User.id == user_pk).first()
    if user is None:
        raise HTTPException(status_code=401, detail="usuário da sessão não existe")
    return user


def require_session_person(user: User = Depends(get_current_person)) -> User:
    """Operações de gestão (onboarding, tokens) exigem sessão da UI.

    Quando o ``AuthMiddleware`` resolveu outra credencial (agent_token/team) na
    mesma requisição, nega com 403 mesmo que um JWT válido acompanhe.
    """
    method = auth_method_var.get()
    if method and method != "session":
        raise HTTPException(
            status_code=403,
            detail="esta operação exige a sessão da UI (login Google)",
        )
    return user


def _require_allowed_domain() -> str:
    """Fail-closed: sem domínio configurado nenhum login é aceito."""
    domain = _allowed_domain()
    if not domain:
        raise HTTPException(
            status_code=503, detail="AUTH_ALLOWED_DOMAIN não configurado"
        )
    return domain


def _complete_google_login(claims: dict, db: Session) -> LoginResponse:
    """Caminho ÚNICO de conclusão do login Google (redirect e device flow).

    Valida o domínio corporativo (claim ``hd`` == ``AUTH_ALLOWED_DOMAIN``
    configurado no install), faz upsert da pessoa (chave = ``sub``) e emite o
    JWT de sessão. Qualquer mecanismo de login DEVE passar por aqui — é o que
    garante que só a conta corporativa configurada entra.
    """
    domain = _require_allowed_domain()

    # Conta sem claim ``hd`` é conta pessoal (não gerenciada) — recusada.
    hosted_domain = str(claims.get("hd") or "").strip().lower()
    if hosted_domain != domain:
        raise HTTPException(
            status_code=403,
            detail=f"acesso restrito a contas Google do domínio {domain}",
        )

    sub = str(claims["sub"])
    email = claims.get("email")
    name = claims.get("name")
    picture = claims.get("picture")

    user = db.query(User).filter(User.google_sub == sub).first()
    created_now = user is None
    if created_now:
        user = User(
            user_id=sub,
            user_type=USER_TYPE_PERSON,
            google_sub=sub,
            email=email,
            name=name,
            display_name=name,
            avatar_url=picture,
        )
        db.add(user)
    else:
        # Atualiza dados informativos; a chave da pessoa é sempre o ``sub``.
        user.email = email or user.email
        user.display_name = name or user.display_name
        user.avatar_url = picture or user.avatar_url
    db.commit()
    db.refresh(user)

    # ``first_login`` = pessoa criada nesta chamada. O estado "precisa de
    # onboarding" (sem máquina vinculada) é consultável em ``GET /auth/me``.
    token = issue_session_jwt(
        user_id=user.id, email=user.email or "", name=user.display_name or ""
    )
    return LoginResponse(
        access_token=token, first_login=created_now, user=UserOut.model_validate(user)
    )


@router.post("/google", response_model=LoginResponse)
def login_with_google(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    _require_allowed_domain()
    try:
        claims = _verify_google_id_token(payload.id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="ID token do Google inválido")
    return _complete_google_login(claims, db)


class MachineSuggestionsResponse(BaseModel):
    detected_hostname: Optional[str] = None
    unlinked_hostnames: list = []
    suggested_group: Optional[str] = None


def _client_ip(request) -> Optional[str]:
    """IP do navegador: primeiro hop do X-Forwarded-For (Traefik) ou conexão."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = getattr(request, "client", None)
    return client.host if client else None


def _reverse_dns_hostname(ip: str) -> Optional[str]:
    """Nome curto da máquina via DNS reverso (isolada p/ monkeypatch em teste).

    Em LANs corporativas (AD/DHCP) o IP do PC costuma resolver para o próprio
    nome da máquina. Best-effort: qualquer falha retorna None.
    """
    import socket

    try:
        fqdn = socket.gethostbyaddr(ip)[0]
    except Exception:  # noqa: BLE001 - sugestão é opcional
        return None
    short = fqdn.split(".")[0].strip()
    return short or None


@router.get("/machine-suggestions", response_model=MachineSuggestionsResponse)
def machine_suggestions(
    request: Request,
    user: User = Depends(require_session_person),
    db: Session = Depends(get_db),
):
    """Sugestões para o campo 'máquina' do onboarding (feature auth Google).

    ``detected_hostname``: DNS reverso do IP do navegador — quando o nome
    detectado bate (case-insensitive) com uma máquina já conhecida, devolve a
    grafia exata do cadastro. ``unlinked_hostnames``: máquinas legadas ainda sem
    dono, para o autocomplete.
    """
    unlinked = [
        m.hostname
        for m in db.query(Machine)
        .filter(Machine.status == MachineStatus.unlinked)
        .order_by(Machine.hostname)
        .all()
    ]

    detected: Optional[str] = None
    ip = _client_ip(request)
    if ip and ip not in ("127.0.0.1", "::1", "testclient"):
        detected = _reverse_dns_hostname(ip)
    if detected:
        known = {
            m.hostname.casefold(): m.hostname
            for m in db.query(Machine).all()
        }
        detected = known.get(detected.casefold(), detected)

    suggested_group: Optional[str] = None
    if detected:
        legacy = (
            db.query(User)
            .filter(
                User.user_id == detected,
                User.user_type == USER_TYPE_LEGACY_HOST,
            )
            .first()
        )
        if legacy is not None and legacy.group is not None:
            suggested_group = legacy.group.name

    return MachineSuggestionsResponse(
        detected_hostname=detected,
        unlinked_hostnames=unlinked,
        suggested_group=suggested_group,
    )


@router.get("/me", response_model=MeResponse)
def me(
    user: User = Depends(get_current_person),
    db: Session = Depends(get_db),
):
    machine = _linked_machine(db, user)
    group_name = _effective_group_name(db, user, machine)
    return MeResponse(
        user=UserOut.model_validate(user),
        machine=MachineOut.model_validate(machine) if machine is not None else None,
        group=group_name,
    )


# ---------------------------------------------------------------------------
# Device Flow (ADR-007): login Google sem URL de redirect
# ---------------------------------------------------------------------------
# Fluxo "TVs e dispositivos de entrada limitada": funciona com a UI em IP
# interno/HTTP porque o Google nunca redireciona para o servidor. O ID token
# recebido no polling passa pelo MESMO ``_complete_google_login`` do fluxo de
# redirect — a restrição ao domínio corporativo configurado no install vale
# igualmente aqui.

GOOGLE_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


def _google_oauth_client() -> tuple:
    """Credencial usada pelo device flow.

    Preferência: ``GOOGLE_DEVICE_CLIENT_ID/SECRET`` (client tipo "TVs e
    dispositivos de entrada limitada"); fallback: ``GOOGLE_CLIENT_ID/SECRET``
    (instalações que usam um único client).
    """
    device_id = os.getenv("GOOGLE_DEVICE_CLIENT_ID", "").strip()
    device_secret = os.getenv("GOOGLE_DEVICE_CLIENT_SECRET", "").strip()
    if device_id and device_secret:
        return device_id, device_secret
    return (
        os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
    )


def _post_form(url: str, data: dict) -> dict:
    """POST form-encoded ao Google; isolada para monkeypatch nos testes.

    Devolve o JSON do corpo com ``_status`` (HTTP) anexado — o device flow usa
    códigos de erro no corpo (``authorization_pending`` etc.) com status 4xx.
    """
    import httpx

    response = httpx.post(url, data=data, timeout=10)
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - corpo não-JSON vira erro genérico
        body = {}
    body["_status"] = response.status_code
    return body


class DeviceStartResponse(BaseModel):
    device_code: str
    user_code: str
    verification_url: str
    interval: int = 5
    expires_in: int


class DevicePollRequest(BaseModel):
    device_code: str


class DevicePollResponse(BaseModel):
    status: str  # "pending" | "slow_down" | "ok"
    access_token: Optional[str] = None
    token_type: str = "bearer"
    first_login: Optional[bool] = None
    user: Optional[UserOut] = None


def _require_device_flow_config() -> tuple:
    _require_allowed_domain()
    client_id, client_secret = _google_oauth_client()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET não configurados",
        )
    return client_id, client_secret


@router.post("/google/device/start", response_model=DeviceStartResponse)
def device_flow_start():
    """Inicia o device flow: devolve o código que o usuário digita no Google."""
    client_id, _ = _require_device_flow_config()
    body = _post_form(
        GOOGLE_DEVICE_CODE_URL,
        {"client_id": client_id, "scope": "openid email profile"},
    )
    if body.get("_status") != 200 or not body.get("device_code"):
        raise HTTPException(
            status_code=502,
            detail="não foi possível iniciar o login com o Google (device flow)",
        )
    return DeviceStartResponse(
        device_code=body["device_code"],
        user_code=body["user_code"],
        verification_url=body.get("verification_url")
        or body.get("verification_uri")
        or "https://google.com/device",
        interval=int(body.get("interval") or 5),
        expires_in=int(body.get("expires_in") or 1800),
    )


@router.post("/google/device/poll", response_model=DevicePollResponse)
def device_flow_poll(payload: DevicePollRequest, db: Session = Depends(get_db)):
    """Consulta o Google; quando autorizado, conclui o login pelo caminho único."""
    client_id, client_secret = _require_device_flow_config()
    body = _post_form(
        GOOGLE_TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "device_code": payload.device_code,
            "grant_type": _DEVICE_GRANT_TYPE,
        },
    )

    error = str(body.get("error") or "")
    if error == "authorization_pending":
        return DevicePollResponse(status="pending")
    if error == "slow_down":
        return DevicePollResponse(status="slow_down")
    if error == "expired_token":
        raise HTTPException(
            status_code=410, detail="código expirado — recomece o login"
        )
    if error == "access_denied":
        raise HTTPException(status_code=403, detail="autorização negada no Google")
    if body.get("_status") != 200 or not body.get("id_token"):
        raise HTTPException(
            status_code=502, detail="resposta inesperada do Google no device flow"
        )

    try:
        claims = _verify_google_id_token(body["id_token"])
    except Exception:
        raise HTTPException(status_code=401, detail="ID token do Google inválido")
    login = _complete_google_login(claims, db)
    return DevicePollResponse(
        status="ok",
        access_token=login.access_token,
        first_login=login.first_login,
        user=login.user,
    )


# ---------------------------------------------------------------------------
# Onboarding: vínculo máquina→conta (ADR-004/ADR-005)
# ---------------------------------------------------------------------------

LINK_ACTION_LINK = "link"
LINK_ACTION_CONFLICT = "conflict_detected"


class OnboardingRequest(BaseModel):
    hostname: str
    group_name: Optional[str] = None


class OnboardingResponse(BaseModel):
    linked: bool
    hostname: str
    group: str
    memories_count: int
    legacy_user_linked: bool


def _count_memories_for_hostname(hostname: str) -> int:
    """Contagem best-effort das memórias com este hostname no payload (Qdrant).

    Informativa para a UX de onboarding — nunca lê/escreve payloads e qualquer
    falha resulta em 0 (não bloqueia o vínculo).
    """
    try:
        from qdrant_client import models as qmodels

        from app.utils.memory import get_memory_client_safe

        client = get_memory_client_safe()
        vector_store = getattr(client, "vector_store", None)
        qdrant = getattr(vector_store, "client", None)
        collection = getattr(vector_store, "collection_name", None)
        if qdrant is None or not collection:
            return 0
        result = qdrant.count(
            collection_name=collection,
            count_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="hostname", match=qmodels.MatchValue(value=hostname)
                    )
                ]
            ),
            exact=True,
        )
        return int(getattr(result, "count", 0) or 0)
    except Exception:  # noqa: BLE001 — contagem informativa, nunca bloqueia
        return 0


@router.post("/onboarding", response_model=OnboardingResponse)
def onboarding(
    payload: OnboardingRequest,
    user: User = Depends(require_session_person),
    db: Session = Depends(get_db),
):
    """Vincula a máquina informada à pessoa autenticada e aplica o grupo escolhido.

    Máquina de outra conta ⇒ 409 + estado ``conflict`` + trilha auditável —
    nunca vincula automaticamente (PRD "Regras de migração"). Repetição pela
    mesma pessoa é idempotente. Nenhum payload do Qdrant é tocado (ADR-005).
    """
    if not (payload.hostname or "").strip():
        raise HTTPException(status_code=422, detail="hostname obrigatório")
    try:
        hostname = require_sysmo_hostname(payload.hostname)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    machine, legacy_user = resolve_or_create_machine(db, hostname)
    hostname = machine.hostname

    # Conflito: máquina pertence a outra conta — bloqueia e registra.
    if machine.linked_user_id is not None and machine.linked_user_id != user.id:
        machine.status = MachineStatus.conflict
        db.add(
            LinkAuditLog(
                machine_id=machine.id,
                actor_user_id=user.id,
                action=LINK_ACTION_CONFLICT,
                detail={
                    "hostname": hostname,
                    "linked_user_id": str(machine.linked_user_id),
                },
            )
        )
        db.commit()
        invalidate_identity_link_cache(hostname)
        raise HTTPException(
            status_code=409,
            detail=(
                "máquina já vinculada a outra conta; o conflito foi registrado "
                "para tratamento administrativo"
            ),
        )

    already_linked = (
        machine.linked_user_id == user.id and machine.status == MachineStatus.linked
    )

    explicit_group = normalize_group_name(payload.group_name)
    if explicit_group is None and legacy_user is not None and legacy_user.group_id is not None:
        group = legacy_user.group
    else:
        group = get_or_create_group(db, payload.group_name)

    user.group_id = group.id
    if legacy_user is not None:
        legacy_user.group_id = group.id

    backfill_legacy_user_id(machine, legacy_user)

    if not already_linked:
        machine.linked_user_id = user.id
        machine.status = MachineStatus.linked
        machine.linked_at = get_current_utc_time()
        machine.linked_by = user.id
        backfill_legacy_user_id(machine, legacy_user)
        db.add(
            LinkAuditLog(
                machine_id=machine.id,
                actor_user_id=user.id,
                action=LINK_ACTION_LINK,
                detail={
                    "hostname": hostname,
                    "group": group.name,
                    "legacy_user_id": (
                        str(machine.legacy_user_id) if machine.legacy_user_id else None
                    ),
                },
            )
        )
    db.commit()
    invalidate_identity_link_cache(hostname)

    return OnboardingResponse(
        linked=True,
        hostname=hostname,
        group=group.name,
        memories_count=_count_memories_for_hostname(hostname),
        legacy_user_linked=machine.legacy_user_id is not None,
    )
