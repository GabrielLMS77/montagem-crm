# Emissao de NFS-e em homologacao

## Seguranca e configuracao local

- Use somente `NFSE_ENV=restricted`. A rota rejeita qualquer outro ambiente ou URL.
- O emissor exige `NFSE_EMISSION_TOKEN` com pelo menos 32 caracteres. Gere um token localmente com `python -c "import secrets; print(secrets.token_urlsafe(32))"` e guarde-o apenas no `.env`.
- Configure `NFSE_DPS_SERIES` com uma serie exclusiva para as DPS emitidas por esta aplicacao. O numero da DPS e derivado do identificador da venda; nao reutilize a mesma serie para emissoes feitas por outro sistema.
- Preencha `NFSE_PROVIDER_SPECIAL_TAX_REGIME` conforme orientacao contabil. Para ME/EPP optante pelo Simples Nacional, `NFSE_PROVIDER_SIMPLE_NATIONAL=3`. O campo `NFSE_PROVIDER_SIMPLE_TAX_REGIME` somente deve ser preenchido conforme a orientacao contabil.
- Os XMLs assinados e autorizados ficam em `NFSE_OUTPUT_DIR`, ignorado pelo Git. Nao compartilhe esses arquivos: podem conter dados do tomador.

## Codigos de servico

As variaveis `NFSE_SERVICE_CODE_*` guardam o codigo nacional `cTribNac`, com seis digitos. O modelo usa o catalogo nacional informado na documentacao oficial:

| Variavel | Codigo nacional | Descricao do catalogo |
| --- | ---: | --- |
| `NFSE_SERVICE_CODE_PSYCHOLOGY` | `041601` | Psicologia |
| `NFSE_SERVICE_CODE_PSYCHOTECHNIC_DETRAN` | `170901` | Pericias, laudos e exames tecnicos |
| `NFSE_SERVICE_CODE_PSYCHOTECHNIC_PF` | `170901` | Pericias, laudos e exames tecnicos |
| `NFSE_SERVICE_CODE_TOXICOLOGICAL_ANALYSIS` | `040201` | Analises clinicas |
| `NFSE_SERVICE_CODE_TOXICOLOGICAL_COLLECTION` | `042001` | Coleta de materiais biologicos |
| `NFSE_SERVICE_CODE_PSYCHIATRY` | `040101` | Medicina |
| `NFSE_SERVICE_CODE_FORENSIC_REPORT` | `170901` | Pericias e laudos tecnicos |

Os codigos `NFSE_SERVICE_MUNICIPAL_CODE_*` sao locais, tem tres digitos e so devem ser preenchidos com o codigo confirmado pelo municipio. O item 17.08 da lista nacional corresponde a franquia; pericias, exames e laudos tecnicos aparecem no item 17.09. Confirme com a contabilidade se o enquadramento da atividade corresponde a descricao nacional antes de transmitir.

## Rota

O endpoint `POST /nfse/sales/{sale_id}/emit` aceita chamadas apenas de loopback e usa a venda existente para obter valor, tomador e numero DPS. A competencia e informada no corpo. Envie o token no cabecalho `X-NFSE-Emission-Token` e os dados fiscais especificos:

```json
{
  "service_key": "psychiatry",
  "competence_date": "2026-10-26",
  "service_municipality_code": "1234567",
  "fiscal_description": "Consulta medica",
  "iss_taxation": "1",
  "iss_withholding": "1",
  "municipal_tax_code": null
}
```

O codigo de municipio acima e ilustrativo; use o codigo IBGE real do local da prestacao. `iss_taxation` aceita 1 (tributavel), 2 (imunidade), 3 (exportacao) ou 4 (nao incidencia). `iss_withholding` aceita 1 (sem retencao), 2 (retido pelo tomador) ou 3 (retido pelo intermediario). Confirme esses valores com a contabilidade. Nao inclua diagnostico ou dados clinicos na descricao fiscal.

Antes da chamada, confira o corpo no Swagger local (`/docs`). Uma resposta `201` retorna apenas o status e a chave de acesso; nao retorna o XML. A rota valida a DPS no XSD, assina com o certificado e envia para Producoes Restritas. A primeira chamada e uma transmissao real ao ambiente de homologacao.

Cada venda recebe uma reserva local para evitar uma segunda tentativa acidental. Se a rede cair ou a SEFIN nao confirmar a resposta, consulte a situacao na SEFIN antes de reenviar. O teste automatizado da montagem usa dados sinteticos e o XSD local; ele nao chama a SEFIN.

Se a SEFIN confirmar que nenhuma NFS-e foi gerada, remova manualmente o arquivo `.dps-<serie>-<id-da-venda>.reserved` dentro de `NFSE_OUTPUT_DIR` para permitir uma nova tentativa. Nao remova a reserva se a situacao continuar incerta.
