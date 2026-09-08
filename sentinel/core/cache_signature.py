# sentinel/core/cache_signature.py
"""
Fonte única de verdade para o "perfil de confiança" do cliente usado pelo
semantic cache. NUNCA usar state["risk_level"] (risco da disputa atual,
calculado pela triagem) aqui — isso é outro conceito, com outro vocabulário,
e foi a causa do bug anterior (cache nunca mais dava HIT).

Ajuste os cortes abaixo (LTV_ALTO_MIN etc.) para a distribuição real dos
seus clientes — os valores atuais são só um ponto de partida coerente com
o seed_db.py atual.
"""

LTV_ALTO_MIN = 5000.0
LTV_MEDIO_MIN = 800.0


def get_ltv_tier(ltv: float) -> str:
    ltv = float(ltv or 0.0)
    if ltv >= LTV_ALTO_MIN:
        return "LTV_ALTO"
    if ltv >= LTV_MEDIO_MIN:
        return "LTV_MEDIO"
    return "LTV_BAIXO"


def get_dispute_tier(previous_disputes: int, no_show_count: int, total_orders: int) -> str:
    disputes = int(previous_disputes or 0)
    no_shows = int(no_show_count or 0)
    orders = max(int(total_orders or 0), 1)
    rate = disputes / orders

    if disputes >= 10 or no_shows >= 3 or rate >= 0.15:
        return "HISTORICO_RUIM"
    if disputes >= 3 or no_shows >= 1 or rate >= 0.05:
        return "HISTORICO_MEDIO"
    return "HISTORICO_LIMPO"


def get_wait_time_tier(minutes) -> str:
    if minutes is None:
        return "SEM_DADO"
    if minutes <= 5:
        return "DENTRO_DO_PRAZO"
    if minutes <= 10:
        return "ATRASO_LEVE"
    return "ATRASO_CRITICO"


def build_trust_signature(profile: dict) -> dict:
    """Único ponto que decide o 'bucket de confiança' — chamado tanto no
    save quanto no check do cache, sempre a partir do MESMO dado (a row de
    customer_profiles), nunca do risk_level da disputa atual."""
    return {
        "risk_tier": str(profile.get("risk_score", "HIGH")).upper(),
        "ltv_tier": get_ltv_tier(profile.get("lifetime_value_brl", 0.0)),
        "dispute_tier": get_dispute_tier(
            profile.get("previous_disputes", 0),
            profile.get("no_show_count", 0),
            profile.get("total_orders", 0),
        ),
        "account_type": str(profile.get("account_type", "B2C")).upper(),
    }


def signature_to_text(sig: dict) -> str:
    """Texto bucketizado que entra no embedding no lugar dos números crus
    do histórico do cliente — isso é o que permite dois clientes diferentes
    com perfil parecido caírem perto no espaço vetorial."""
    return (
        f"[Perfil de Confiança] Risco={sig['risk_tier']} "
        f"LTV={sig['ltv_tier']} Historico={sig['dispute_tier']} "
        f"Tipo={sig['account_type']}"
    )