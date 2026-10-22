# Integração NFS-e Nacional

O cliente usa a API REST da SEFIN Nacional com mTLS. A base de Produção Restrita é https://sefin.producaorestrita.nfse.gov.br/SefinNacional. Para produção, configure NFSE_ENV=production. A raiz https://nfse.gov.br é um portal web, não o host REST.

## Configuração

1. Instale as dependências com pip install -r requirements.txt.
2. Copie .env.example para .env e configure NFSE_PFX_PATH e NFSE_PFX_PASSWORD.
3. O XSD DPS v1.01 da Produção Restrita está em schemas/nfse/producao-restrita/DPS_v1.01.xsd.
4. Mantenha certificado, senha e XMLs emitidos fora do controle de versão.

## Uso

O chamador pode montar infDPS com DpsElement (nome local, texto, atributos e filhos) ou fornecer um elemento lxml/XML. Em ambos os casos, a ordem e os campos seguem o XSD vigente. O cliente cria o envelope DPS, valida o XML, assina a referência ao atributo Id e valida novamente antes de transmitir.

    from lxml import etree
    from clinicaflow.fiscal.nfse import DpsElement, NfseClient
    from clinicaflow.fiscal.nfse.config import NfseSettings
    from clinicaflow.fiscal.nfse.client import configure_nfse_logging

    configure_nfse_logging()
    settings = NfseSettings.from_env()
    inf_dps = etree.parse("dps-infDPS.xml").getroot()
    result = NfseClient(settings).emitir(inf_dps)
    print(result.access_key)
    print(result.authorized_xml_path)

O XML de entrada precisa ser somente o elemento infDPS, no namespace nacional, com Id válido e campos exigidos pelo esquema vigente. O XSD rejeita estruturas incompletas antes da chamada à SEFIN.

O POST /nfse recebe JSON com dpsXmlGZipB64. A resposta nfseXmlGZipB64 é decodificada, interpretada e gravada junto com a DPS assinada em NFSE_OUTPUT_DIR.
