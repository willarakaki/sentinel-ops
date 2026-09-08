from sentinel.agents.security_shield import MAX_INPUT_CHARS, check_payload_size


def test_payload_dentro_do_limite_deve_passar():
    texto_valido = "Meu lanche chegou frio e o refrigerante veio violado."
    assert check_payload_size(texto_valido) is False

def test_payload_no_limite_exato_deve_passar():
    texto_limite = "A" * MAX_INPUT_CHARS
    assert check_payload_size(texto_limite) is False

def test_payload_acima_do_limite_deve_bloquear():
    texto_excedente = "A" * (MAX_INPUT_CHARS + 1)
    assert check_payload_size(texto_excedente) is True

def test_payload_massivo_ataque_dow_deve_bloquear():
    payload_massivo = "FRAUDE " * 10000
    assert check_payload_size(payload_massivo) is True