import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts import pacote_agenda_financeiro_taxas as pacote


class PacoteAgendaTaxasTests(unittest.TestCase):
    def test_pacote_inclui_modulos_testes_e_componente_sem_dados_privados(self):
        raiz = Path(__file__).resolve().parents[1]
        for pasta in ('dsystem_erp', 'modules', 'tests'):
            for arquivo in (raiz / pasta).rglob('*.py'):
                self.assertIn(arquivo.relative_to(raiz).as_posix(), pacote.ARQUIVOS)
        self.assertIn('dsystem_erp/components/kanban/index.html', pacote.ARQUIVOS)
        self.assertEqual(len(pacote.ARQUIVOS), len(set(pacote.ARQUIVOS)))
        for nome in pacote.ARQUIVOS:
            self.assertTrue((raiz / nome).is_file(), nome)
            self.assertNotIn(Path(nome).suffix.lower(), ('.db', '.sql', '.pfx', '.pem', '.env'))

    def test_aplicar_confere_conteudo_preserva_backup_e_nao_toca_dados(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp) / 'projeto'
            raiz.mkdir()
            (raiz / 'orcamento.py').write_text('VERSAO_ANTIGA=1', encoding='utf-8')
            (raiz / 'banco.db').write_bytes(b'NAO ALTERAR')
            python = raiz / '.venv/bin/python'
            python.parent.mkdir(parents=True)
            python.touch()
            arquivo = Path(tmp) / 'pacote.zip'
            dados = {nome: b'VERSAO_NOVA=2' if nome.endswith('.py') else b'Teste' for nome in pacote.ARQUIVOS}
            with ZipFile(arquivo,'w') as zipfile:
                for nome, conteudo in dados.items():
                    zipfile.writestr(nome, conteudo)
                zipfile.writestr('manifesto.json', json.dumps({nome:hashlib.sha256(c).hexdigest() for nome,c in dados.items()}))
            with patch.object(pacote.subprocess,'run',return_value=SimpleNamespace(stdout='')) as executar:
                pacote.aplicar(arquivo,raiz)
            self.assertEqual(executar.call_count, 2)
            self.assertEqual((raiz/'orcamento.py').read_bytes(),b'VERSAO_NOVA=2')
            self.assertEqual((raiz/'banco.db').read_bytes(),b'NAO ALTERAR')
            backups = list((raiz/'backups_codigo').glob('*.zip'))
            self.assertEqual(len(backups),1)
            with ZipFile(backups[0]) as zip_backup:
                self.assertEqual(zip_backup.read('orcamento.py'),b'VERSAO_ANTIGA=1')

    def test_pacote_com_arquivo_fora_da_lista_bloqueia_antes_de_alterar(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz/'orcamento.py').write_bytes(b'ANTIGO')
            python = raiz/'.venv/bin/python'
            python.parent.mkdir(parents=True)
            python.touch()
            arquivo = raiz/'pacote.zip'
            with ZipFile(arquivo,'w') as zipfile:
                zipfile.writestr('../fora.py','ERRADO')
            with self.assertRaisesRegex(ValueError,'não corresponde'):
                pacote.aplicar(arquivo,raiz)
            self.assertEqual((raiz/'orcamento.py').read_bytes(),b'ANTIGO')
            self.assertFalse((raiz/'backups_codigo').exists())
