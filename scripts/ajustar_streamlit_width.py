from pathlib import Path


arquivo = Path(__file__).resolve().parents[1] / "orcamento.py"
texto = arquivo.read_text(encoding="utf-8-sig")
texto = texto.replace("use_container_width=True", 'width="stretch"')
texto = texto.replace("use_container_width=False", 'width="content"')
arquivo.write_text(texto, encoding="utf-8")
print("OK")
