"""Gera uma prévia fictícia do espelho para conferência visual local."""
from pathlib import Path
from dsystem_erp.services.faturamento_espelho import gerar_pdf_espelho_faturamento

if __name__ == "__main__":
    destino = Path("output/pdf")
    destino.mkdir(parents=True, exist_ok=True)
    dados = {"id": 42, "cliente": "Cliente de demonstração", "cnpj": "",
        "data_lanc": "2026-09-02", "medicao_inicio": "2026-08-01", "vencimento": "2026-09-07",
        "forma_pag": "PIX", "valor_total": 570, "obs_nota": "Serviços prestados na competência Agosto/2026.",
        "itens": [{"desc": "Mensalidade competência Agosto/2026 (04 desktops)", "qtd": 1, "vunit": 240, "vtotal": 240},
                  {"desc": "Backup em nuvem (2/12 parcela)", "qtd": 1, "vunit": 330, "vtotal": 330}]}
    (destino / "previa_espelho.pdf").write_bytes(gerar_pdf_espelho_faturamento(dados, {"id": 25, "endereco": "Endereço de demonstração", "cidade_estado": "Belo Horizonte / MG"}))
