"""Gera apenas amostras locais com dados fictícios; não acessa banco/impressora."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dsystem_erp.services.recepcao_kanban import gerar_etiqueta_equipamento


if __name__ == "__main__":
    pasta = Path(__file__).resolve().parents[1] / "tmp" / "pdfs" / "etiqueta-os"
    pasta.mkdir(parents=True, exist_ok=True)
    item = dict(id=123, os_id=37, numero_item="00037-A", cliente="CLIENTE DE TESTE - EMPRESA EXEMPLO LTDA",
                equipamento="Câmera da entrada principal", marca="Fabricante / Modelo de teste",
                numero_serie="ABC123456789", servico="Trocar conector e testar a imagem. Conferir alimentação e cabos.",
                configuracao='{"backup":"Sim"}')
    for largura, altura in ((100, 50), (70, 40)):
        destino = pasta / f"etiqueta-{largura}x{altura}.pdf"
        destino.write_bytes(gerar_etiqueta_equipamento(item, "https://erp.example.test", largura, altura))
        print(destino)
    destino_i8 = pasta / "cupom-elgin-i8-80x60.pdf"
    destino_i8.write_bytes(gerar_etiqueta_equipamento(item, "https://erp.example.test", 80, 60, 4))
    print(destino_i8)
