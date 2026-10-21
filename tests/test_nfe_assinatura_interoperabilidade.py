"""Regressões contra C14N inconsistente, incluindo outro motor XMLDSig (.NET)."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from lxml import etree
from dsystem_erp.services.nfe_produto import (
    canonicalizar_elemento_nfe, montar_envelope_nfe_autorizacao,
    validar_assinatura_nfe_produto,
)
from tests import test_nfe_produto as fixtures

DS = 'http://www.w3.org/2000/09/xmldsig#'
POWERSHELL = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'


def verificar_dotnet(xml):
    proc = subprocess.run(
        [str(POWERSHELL), '-NoProfile', '-NonInteractive', '-Command',
         Path(__file__).with_name('verificar_nfe_dotnet.ps1').read_text(encoding='utf-8')],
        input=xml, capture_output=True, timeout=25,
    )
    if proc.returncode:
        raise AssertionError(proc.stderr.decode('utf-8', errors='replace'))
    return json.loads(proc.stdout.decode('utf-8-sig'))


class InteroperabilidadeNFeTests(unittest.TestCase):
    def test_c14n_troca_namespace_padrao_nao_inventa_xmlns_vazio(self):
        raiz = etree.fromstring(
            f'<NFe xmlns="urn:nfe"><Signature xmlns="{DS}">'
            '<SignedInfo><Reference URI="#NFe123"><Transforms><Transform Algorithm="urn:alg"/>'
            '</Transforms><DigestValue>abc</DigestValue></Reference></SignedInfo></Signature></NFe>'.encode())
        si = raiz.find(f'.//{{{DS}}}SignedInfo')
        original = etree.tostring(raiz)
        esperado = (f'<SignedInfo xmlns="{DS}"><Reference URI="#NFe123">'
                    '<Transforms><Transform Algorithm="urn:alg"></Transform></Transforms>'
                    '<DigestValue>abc</DigestValue></Reference></SignedInfo>').encode()
        self.assertEqual(canonicalizar_elemento_nfe(si), esperado)
        self.assertEqual(etree.tostring(raiz), original)

    def test_c14n_preserva_namespace_e_atributos_ancestrais_inclusivos(self):
        raiz = etree.fromstring(
            b'<Envelope xmlns="urn:soap" xmlns:s="urn:prefixo" xml:lang="pt" xml:space="preserve">'
            b'<Body xml:lang="en"><Signature xmlns="urn:ds"><SignedInfo>'
            b'<Reference/></SignedInfo></Signature></Body></Envelope>')
        si = raiz.find('.//{urn:ds}SignedInfo')
        esperado = (b'<SignedInfo xmlns="urn:ds" xmlns:s="urn:prefixo" xml:lang="en" xml:space="preserve">'
                    b'<Reference></Reference></SignedInfo>')
        self.assertEqual(canonicalizar_elemento_nfe(si), esperado)

    def test_assinatura_gerada_com_c14n_errado_nao_passara_no_validador(self):
        # Replica explicitamente o erro observado na nota real: resets espúrios
        # de namespace abaixo de Reference, usados no cálculo da assinatura.
        def c14n_antigo(elemento):
            correto = canonicalizar_elemento_nfe(elemento)
            if elemento.tag == f'{{{DS}}}SignedInfo':
                for nome in (b'Transforms', b'Transform', b'DigestMethod', b'DigestValue'):
                    correto = correto.replace(b'<' + nome + b'>', b'<' + nome + b' xmlns="">')
                    correto = correto.replace(b'<' + nome + b' Algorithm=', b'<' + nome + b' xmlns="" Algorithm=')
            return correto

        with patch('dsystem_erp.services.nfe_produto.canonicalizar_elemento_nfe', side_effect=c14n_antigo):
            antiga, _ = fixtures.NFeProdutoTests().xml_assinado_teste()
        for xml in (antiga, montar_envelope_nfe_autorizacao(antiga)):
            with self.assertRaisesRegex(ValueError, 'Assinatura NF-e inválida'):
                validar_assinatura_nfe_produto(xml)
        if POWERSHELL.exists():
            self.assertFalse(verificar_dotnet(antiga)['valida'])

    @unittest.skipUnless(POWERSHELL.exists(), 'Validador independente .NET Framework disponível no Windows')
    def test_assinatura_e_soap_aceitos_por_motor_independente_dotnet(self):
        assinado, _ = fixtures.NFeProdutoTests().xml_assinado_teste()
        si = etree.fromstring(assinado).find(f'.//{{{DS}}}SignedInfo')
        esperado = hashlib.sha256(canonicalizar_elemento_nfe(si)).hexdigest()
        for xml in (assinado, montar_envelope_nfe_autorizacao(assinado)):
            resultado = verificar_dotnet(xml)
            self.assertTrue(resultado['valida'], resultado)
            self.assertEqual(resultado['sha256_signedinfo_c14n'], esperado)


if __name__ == '__main__':
    unittest.main()
