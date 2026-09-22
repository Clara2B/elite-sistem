from app.excel_reader import _normalizar_larguras


def test_normalizar_larguras_preenche_linhas_curtas_com_none():
    rows = [
        ("A", "B", "C"),
        ("1", "2", "3", "4", "5", "6", "7", "8", "9"),
        ("x", "y", "z"),
    ]
    resultado = _normalizar_larguras(rows)
    assert all(len(r) == 9 for r in resultado)
    assert resultado[0] == ("A", "B", "C", None, None, None, None, None, None)
    assert resultado[1] == ("1", "2", "3", "4", "5", "6", "7", "8", "9")
    assert resultado[2] == ("x", "y", "z", None, None, None, None, None, None)


def test_normalizar_larguras_lista_vazia():
    assert _normalizar_larguras([]) == []


def test_normalizar_larguras_ja_uniforme_fica_igual():
    rows = [("A", "B"), ("C", "D")]
    assert _normalizar_larguras(rows) == rows
