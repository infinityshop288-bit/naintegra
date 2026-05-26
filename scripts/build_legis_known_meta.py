#!/usr/bin/env python3
"""Gera web/lex/data/legis_known_meta.json e atualiza legis_summaries.json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "lex" / "data" / "legis_known_meta.json"
CATALOG = ROOT / "web" / "lex" / "data" / "legis_catalog.json"
BODIES = ROOT / "web" / "lex" / "data" / "legis_bodies.json"
SUMMARIES = ROOT / "web" / "lex" / "data" / "legis_summaries.json"

# Chave = fragmento da URL (ex.: l7210, del2848, emc103, lcp101)
KNOWN: dict[str, tuple[str, str, str]] = {
    "constituicao.htm": ("Constituição Federal de 1988", "Estabelece a organização do Estado, direitos fundamentais e a estrutura da República.", "Constituição e Adm."),
    "d22626": ("Decreto 22.626/1933 — Lei da Usura", "Limita juros em contratos e operações de crédito (Lei da Usura).", "Legislação Especial"),
    "d57663": ("Decreto 57.663/1966", "Regulamenta a organização e o funcionamento do Conselho Monetário Nacional e do Banco Central.", "Legislação Especial"),
    "d70235": ("Decreto 70.235/1972 — Regimento Interno do STF", "Aprova o Regimento Interno do Supremo Tribunal Federal.", "Constituição e Adm."),
    "del0911": ("Decreto-Lei 911/1969 — Locação predial urbana", "Dispõe sobre locação de imóveis urbanos e procedimentos correlatos.", "Civil e Trabalho"),
    "del1075": ("Decreto-Lei 1.075/1970", "Altera dispositivos sobre valor provisório de créditos tributários.", "Legislação Especial"),
    "del2848": ("Decreto-Lei 2.848/1940 — Código Penal", "Define crimes e penas do Direito Penal brasileiro (Código Penal).", "Penal e Processual"),
    "del3365": ("Decreto-Lei 3.365/1941 — Desapropriação por utilidade pública", "Regula desapropriação por utilidade pública e dispõe sobre indenização.", "Legislação Especial"),
    "del3688": ("Decreto-Lei 3.688/1941 — Procedimento penal militar", "Estabelece normas de processo penal militar.", "Penal e Processual"),
    "del3689": ("Decreto-Lei 3.689/1941 — Código de Processo Penal", "Estabelece normas de processo penal (CPP).", "Penal e Processual"),
    "del3914": ("Decreto-Lei 3.914/1941", "Dispõe sobre revogação de medida de segurança e regime de internação.", "Penal e Processual"),
    "del3931": ("Decreto-Lei 3.931/1941", "Regula a extradição de estrangeiros e brasileiros.", "Penal e Processual"),
    "del4657": ("Decreto-Lei 4.657/1942 — LINDB", "Introdu a Lei de Introdução às Normas do Direito Brasileiro (LINDB).", "Constituição e Adm."),
    "del5452": ("Decreto-Lei 5.452/1943 — CLT", "Consolida as leis do trabalho (CLT).", "Civil e Trabalho"),
    "del9760": ("Decreto-Lei 9.760/1946", "Dispõe sobre crimes contra a economia popular e ordem econômica.", "Penal e Processual"),
    "l0605": ("Lei 605/1949 — Radiodifusão", "Dispõe sobre radiodifusão sonora e imagens.", "Constituição e Adm."),
    "l1060": ("Lei 1.060/1950 — Assistência judiciária", "Estabelece normas para assistência judiciária gratuita aos necessitados.", "Constituição e Adm."),
    "l1079": ("Lei 1.079/1950 — Impeachment", "Regula processo de julgamento dos crimes de responsabilidade do Presidente.", "Constituição e Adm."),
    "l1521": ("Lei 1.521/1951 — Crimes contra a economia popular", "Altera dispositivos da legislação vigente sobre crimes contra a economia popular.", "Penal e Processual"),
    "l1579": ("Lei 1.579/1952", "Prorroga sessões legislativas e dispõe sobre prazos parlamentares.", "Constituição e Adm."),
    "l2889": ("Lei 2.889/1956 — IPVA", "Institui imposto sobre veículos automotores (IPVA).", "Legislação Especial"),
    "l4090": ("Lei 4.090/1962 — Ações nominativas", "Regula emissão de ações nominativas e negociação de valores mobiliários.", "Legislação Especial"),
    "l4132": ("Lei 4.132/1962 — Sociedades por ações", "Dispõe sobre sociedades por ações e valores mobiliários.", "Legislação Especial"),
    "l4591": ("Lei 4.591/1964 — Condomínios em incorporações", "Regula condomínios em incorporações imobiliárias e propriedade por unidades autônomas.", "Legislação Especial"),
    "l4717": ("Lei 4.717/1965 — Ação popular", "Regula a ação popular e dá outras providências.", "Constituição e Adm."),
    "l4729": ("Lei 4.729/1965 — Valores mobiliários", "Altera normas sobre valores mobiliários e sociedades anônimas.", "Legislação Especial"),
    "l4737": ("Lei 4.737/1965 — Código Eleitoral", "Institui o Código Eleitoral e normas eleitorais.", "Constituição e Adm."),
    "l4749": ("Lei 4.749/1965", "Dispõe sobre nacionalidade e naturalização de estrangeiros.", "Constituição e Adm."),
    "l4886": ("Lei 4.886/1965 — Lei Sindical", "Regula o direito de organização sindical dos trabalhadores e das empresas.", "Constituição e Adm."),
    "l5172": ("Lei 5.172/1966 — CTN", "Dispõe sobre o Sistema Tributário Nacional (CTN).", "Legislação Especial"),
    "l5256": ("Lei 5.256/1967 — Prisão especial", "Regula prisão especial de autoridades e agentes públicos.", "Penal e Processual"),
    "l5474": ("Lei 5.474/1968 — Imprensa", "Altera normas sobre direito de resposta e liberdade de imprensa.", "Constituição e Adm."),
    "l5478": ("Lei 5.478/1968 — Imprensa", "Complementa normas sobre responsabilidade civil da imprensa.", "Constituição e Adm."),
    "l5584": ("Lei 5.584/1970", "Fixa prazos para entrega de laudos periciais em processos judiciais.", "Legislação Especial"),
    "l5764": ("Lei 5.764/1971 — Cooperativas", "Regula organização e funcionamento das sociedades cooperativas.", "Civil e Trabalho"),
    "l5889": ("Lei 5.889/1973", "Altera dispositivos da Consolidação das Leis do Trabalho.", "Civil e Trabalho"),
    "l5941": ("Lei 5.941/1973", "Dispõe sobre suspensão de medida de segurança e internação.", "Penal e Processual"),
    "l6019": ("Lei 6.019/1974", "Altera normas trabalhistas sobre contratos e verbas rescisórias.", "Civil e Trabalho"),
    "l6015": ("Lei 6.015/1973 — Lei de Registros Públicos", "Dispõe sobre os registros públicos e normas a eles relativas.", "Legislação Especial"),
    "l6385": ("Lei 6.385/1976 — CVM", "Institui a Comissão de Valores Mobiliários e regula o mercado de capitais.", "Legislação Especial"),
    "l6515": ("Lei 6.515/1977 — Divórcio", "Altera normas de direito de família e introduz o divórcio.", "Civil e Trabalho"),
    "l6766": ("Lei 6.766/1979 — Parcelamento do solo", "Regula parcelamento do solo urbano e direito urbanístico.", "Legislação Especial"),
    "l6830": ("Lei 6.830/1980 — Execução fiscal", "Regula execução fiscal de créditos tributários da Fazenda Pública.", "Legislação Especial"),
    "l6858": ("Lei 6.858/1980 — Pagamento a terceiros", "Dispõe sobre pagamento, a terceiros, de valores devidos por instituições financeiras a falecidos.", "Legislação Especial"),
    "l6404": ("Lei 6.404/1976 — Lei das S.A.", "Dispõe sobre as sociedades anônimas (Lei das S.A.).", "Legislação Especial"),
    "l6938": ("Lei 6.938/1981 — Política Nacional do Meio Ambiente", "Institui a Política Nacional do Meio Ambiente (PNMA).", "Legislação Especial"),
    "l7210": ("Lei 7.210/1984 — Lei de Execução Penal", "Define normas para execução de penas e medidas alternativas (LEP).", "Penal e Processual"),
    "l7347": ("Lei 7.347/1985 — Ação civil pública", "Regula ação civil pública e tutela de interesses difusos e coletivos.", "Constituição e Adm."),
    "l7357": ("Lei 7.357/1985 — Cheque", "Dispõe sobre o cheque e dá outras providências.", "Civil e Trabalho"),
    "l7418": ("Lei 7.418/1985 — Empréstimo consignado", "Regula empréstimos consignados em folha de pagamento.", "Legislação Especial"),
    "l7492": ("Lei 7.492/1986 — Lei cambial", "Regula duplicata, nota promissória e títulos de crédito (Lei Cambial).", "Civil e Trabalho"),
    "l7716": ("Lei 7.716/1989 — Crimes de preconceito", "Define crimes resultantes de preconceito de raça ou cor.", "Penal e Processual"),
    "l7783": ("Lei 7.783/1989 — Greve", "Regula direito de greve e procedimentos correlatos.", "Civil e Trabalho"),
    "l7960": ("Lei 7.960/1989 — Prisão temporária", "Regula prisão temporária e prazos de custódia.", "Penal e Processual"),
    "l8009": ("Lei 8.009/1990 — Reparação ao consumidor", "Dispõe sobre reparação de danos ao consumidor por produtos e serviços.", "Civil e Trabalho"),
    "l8038": ("Lei 8.038/1990 — Júri", "Altera normas de competência e procedimento do Tribunal do Júri.", "Penal e Processual"),
    "l8036": ("Lei 8.036/1990 — FGTS", "Dispõe sobre o Fundo de Garantia do Tempo de Serviço (FGTS).", "Legislação Especial"),
    "l8069": ("Lei 8.069/1990 — ECA", "Dispõe sobre o Estatuto da Criança e do Adolescente (ECA).", "Legislação Especial"),
    "l8072": ("Lei 8.072/1990 — Crimes hediondos", "Define crimes hediondos e restringe benefícios penais.", "Penal e Processual"),
    "l8078": ("Lei 8.078/1990 — CDC", "Estabelece normas de proteção ao consumidor (CDC).", "Civil e Trabalho"),
    "l8112": ("Lei 8.112/1990 — Servidores públicos", "Regula regime jurídico dos servidores públicos civis da União.", "Constituição e Adm."),
    "l8137": ("Lei 8.137/1990 — Crimes tributários", "Define crimes contra a ordem tributária e economia popular.", "Penal e Processual"),
    "l8176": ("Lei 8.176/1991 — Política energética", "Dispõe sobre a política energética nacional e o monopólio do petróleo.", "Legislação Especial"),
    "l8212": ("Lei 8.212/1991 — Previdência Social", "Dispõe sobre custeio e arrecadação da Previdência Social.", "Civil e Trabalho"),
    "l8213": ("Lei 8.213/1991 — Benefícios da Previdência", "Dispõe sobre Planos de Benefícios da Previdência Social.", "Civil e Trabalho"),
    "l8245": ("Lei 8.245/1991 — Locações", "Regula locações de imóveis urbanos e despejo.", "Civil e Trabalho"),
    "l8429": ("Lei 8.429/1992 — Improbidade administrativa", "Previne e reprime atos de improbidade administrativa.", "Constituição e Adm."),
    "l8629": ("Lei 8.629/1993 — Reforma agrária", "Regula desapropriação de imóvel rural para reforma agrária.", "Legislação Especial"),
    "l8666": ("Lei 8.666/1993 — Licitações", "Regula licitações e contratos administrativos.", "Legislação Especial"),
    "l8906": ("Lei 8.906/1994 — OAB", "Regula exercício da advocacia e organização da OAB.", "Constituição e Adm."),
    "l8934": ("Lei 8.934/1994 — Notários e registradores", "Regula serviços notariais e de registro público.", "Legislação Especial"),
    "l8971": ("Lei 8.971/1995 — Informática", "Regula mercado de informática e propriedade de programas.", "Legislação Especial"),
    "l8987": ("Lei 8.987/1995 — Concessões", "Regula regime de concessão e permissão de serviços públicos.", "Legislação Especial"),
    "l9051": ("Lei 9.051/1995 — Eleições", "Altera normas eleitorais sobre propaganda e financiamento.", "Constituição e Adm."),
    "l9096": ("Lei 9.096/1995 — Partidos políticos", "Regula criação, fusão e funcionamento de partidos políticos.", "Constituição e Adm."),
    "l9099": ("Lei 9.099/1995 — Juizados Especiais", "Institui Juizados Especiais Cíveis e Criminais.", "Penal e Processual"),
    "l9278": ("Lei 9.278/1996 — Privatizações", "Dispõe sobre privatização de empresas públicas e ativos estatais.", "Legislação Especial"),
    "l9279": ("Lei 9.279/1996 — Propriedade industrial", "Regula direitos e obrigações de propriedade industrial.", "Legislação Especial"),
    "l9296": ("Lei 9.296/1996 — Interceptação telefônica", "Regula interceptação telefônica e quebra de sigilo.", "Penal e Processual"),
    "l9307": ("Lei 9.307/1996 — Arbitragem", "Dispõe sobre arbitragem e câmara arbitral.", "Legislação Especial"),
    "l9434": ("Lei 9.434/1997 — DNA e identificação", "Regula cadastro de condenados e identificação genética.", "Penal e Processual"),
    "l9455": ("Lei 9.455/1997 — Tortura", "Define crimes de tortura e mecanismos de prevenção.", "Penal e Processual"),
    "l9469": ("Lei 9.469/1997 — ANEEL", "Autoriza criação da ANEEL e regula setor elétrico.", "Legislação Especial"),
    "l9494": ("Lei 9.494/1997 — Execução contra a Fazenda", "Altera normas de execução contra a Fazenda Pública e processo administrativo fiscal.", "Constituição e Adm."),
    "l9503": ("Lei 9.503/1997 — CTB", "Institui o Código de Trânsito Brasileiro.", "Legislação Especial"),
    "l9504": ("Lei 9.504/1997 — Eleições", "Regula eleições, propaganda eleitoral e financiamento de campanhas.", "Constituição e Adm."),
    "l9507": ("Lei 9.507/1997 — Habeas data", "Regula habeas data e acesso a informações pessoais.", "Constituição e Adm."),
    "l9514": ("Lei 9.514/1997 — Alienação fiduciária", "Regula alienação fiduciária de bens imóveis.", "Civil e Trabalho"),
    "l9601": ("Lei 9.601/1998 — Software", "Altera normas sobre propriedade intelectual de software.", "Legislação Especial"),
    "l9605": ("Lei 9.605/1998 — Crimes ambientais", "Dispõe sobre crimes ambientais e sanções penais.", "Penal e Processual"),
    "l9608": ("Lei 9.608/1998 — Serviços notariais", "Altera normas sobre serviços notariais e registrais.", "Legislação Especial"),
    "l9609": ("Lei 9.609/1998 — Software", "Regula licenciamento e proteção de programas de computador.", "Legislação Especial"),
    "l9610": ("Lei 9.610/1998 — Direitos autorais", "Consolida legislação sobre direitos autorais.", "Legislação Especial"),
    "l9613": ("Lei 9.613/1998 — Lavagem de dinheiro", "Dispõe sobre crimes de lavagem de dinheiro e ocultação de bens.", "Penal e Processual"),
    "l9709": ("Lei 9.709/1998 — ANATEL", "Autoriza criação da ANATEL e regula telecomunicações.", "Legislação Especial"),
    "l9784": ("Lei 9.784/1999 — Processo administrativo", "Regula processo administrativo federal.", "Constituição e Adm."),
    "l9800": ("Lei 9.800/1999 — Conciliação", "Institui audiências de conciliação e mediação em processos judiciais.", "Penal e Processual"),
    "l9807": ("Lei 9.807/1999 — Proteção a vítimas e testemunhas", "Dispõe sobre proteção a vítimas e testemunhas ameaçadas.", "Penal e Processual"),
    "l9868": ("Lei 9.868/1999 — ADI e ADC", "Regula ação declaratória de constitucionalidade e de inconstitucionalidade.", "Constituição e Adm."),
    "l9873": ("Lei 9.873/1999 — Prescrição administrativa", "Estabelece prazo de prescrição para infrações administrativas.", "Constituição e Adm."),
    "l9882": ("Lei 9.882/1999 — ADI, ADC, ADPF e Mandado de Injunção", "Regula ADI, ADC, ADPF e mandado de injunção.", "Constituição e Adm."),
    "l9962": ("Lei 9.962/2000 — ANVISA", "Autoriza criação da ANVISA e regula vigilância sanitária.", "Legislação Especial"),
    "l10101": ("Lei 10.101/2000 — Tempo parcial", "Regula contrato de trabalho em regime de tempo parcial.", "Civil e Trabalho"),
    "l10741": ("Lei 10.741/2003 — Estatuto do Idoso", "Institui o Estatuto do Idoso e normas de proteção à pessoa idosa.", "Legislação Especial"),
    "l10826": ("Lei 10.826/2003 — Estatuto do Desarmamento", "Regula registro, posse e comercialização de armas de fogo e munição (Estatuto do Desarmamento).", "Penal e Processual"),
    "l10257": ("Lei 10.257/2001 — Estatuto da Cidade", "Regula política urbana e direito à cidade.", "Legislação Especial"),
    "l10259": ("Lei 10.259/2001 — Juizados Federais", "Institui Juizados Especiais Cíveis e Criminais no âmbito da Justiça Federal.", "Penal e Processual"),
    "l10406": ("Lei 10.406/2002 — Código Civil", "Introduz o Código Civil brasileiro.", "Civil e Trabalho"),
    "l11079": ("Lei 11.079/2004 — PPP", "Regula parcerias público-privadas (PPP).", "Legislação Especial"),
    "l11101": ("Lei 11.101/2005 — Recuperação judicial", "Regula recuperação judicial, extrajudicial e falência.", "Legislação Especial"),
    "l11107": ("Lei 11.107/2005 — Consórcios públicos", "Regula consórcios públicos e convênios de cooperação.", "Legislação Especial"),
    "l11221": ("Lei 11.221/2006 — CTB (alterações)", "Altera dispositivos do Código de Trânsito Brasileiro.", "Legislação Especial"),
    "l11340": ("Lei 11.340/2006 — Lei Maria da Penha", "Cria mecanismos para coibir violência doméstica e familiar contra a mulher.", "Penal e Processual"),
    "l11343": ("Lei 11.343/2006 — Lei de Drogas", "Institui Sistema Nacional de Políticas Públicas sobre Drogas.", "Penal e Processual"),
    "l11417": ("Lei 11.417/2006 — Diário Oficial eletrônico", "Disciplina publicação oficial eletrônica de atos normativos.", "Constituição e Adm."),
    "l11419": ("Lei 11.419/2006 — Processo digital", "Dispõe sobre informatização do processo judicial.", "Penal e Processual"),
    "l11671": ("Lei 11.671/2008 — Presídios federais", "Dispõe sobre transferência e inclusão de presos em estabelecimentos penais federais de segurança máxima.", "Penal e Processual"),
    "l11705": ("Lei 11.705/2008 — Lei seca", "Estabelece normas sobre consumo de álcool na condução de veículos.", "Legislação Especial"),
    "l11788": ("Lei 11.788/2008 — Estágio", "Regula estágio de estudantes e relação de aprendizado.", "Civil e Trabalho"),
    "l11795": ("Lei 11.795/2008 — Consórcios", "Dispõe sobre sistemas de consórcio.", "Legislação Especial"),
    "l11804": ("Lei 11.804/2008 — Militares e estágio", "Altera normas sobre estágio e serviço militar.", "Legislação Especial"),
    "l12016": ("Lei 12.016/2009 — Mandado de segurança", "Regula mandado de segurança individual e coletivo.", "Constituição e Adm."),
    "l12037": ("Lei 12.037/2009 — Identificação criminal", "Regula identificação criminal e cadastro de condenados.", "Penal e Processual"),
    "l12153": ("Lei 12.153/2009 — Juizados da Fazenda", "Cria Juizados Especiais da Fazenda Pública.", "Constituição e Adm."),
    "l12288": ("Lei 12.288/2010 — Fundo da Cultura", "Institui Fundo Nacional de Cultura e incentivo à cultura.", "Legislação Especial"),
    "l12291": ("Lei 12.291/2010 — Biocombustíveis", "Regula produção e comercialização de biocombustíveis.", "Legislação Especial"),
    "l12318": ("Lei 12.318/2010 — Alienação parental", "Regula guarda compartilhada e combate à alienação parental.", "Civil e Trabalho"),
    "l12414": ("Lei 12.414/2011 — Cadastro de bons antecedentes", "Institui cadastro nacional de bons antecedentes.", "Penal e Processual"),
    "l12506": ("Lei 12.506/2011 — Terceirização", "Altera normas trabalhistas sobre terceirização e aviso prévio.", "Civil e Trabalho"),
    "l12527": ("Lei 12.527/2011 — LAI", "Regula acesso a informações públicas (Lei de Acesso à Informação).", "Constituição e Adm."),
    "l12529": ("Lei 12.529/2011 — CADE", "Estrutura defesa da concorrência e regulação do CADE.", "Legislação Especial"),
    "l12562": ("Lei 12.562/2011 — Crimes de trânsito", "Altera normas penais sobre crimes de trânsito.", "Penal e Processual"),
    "l12594": ("Lei 12.594/2012 — Sinase", "Institui Sistema Nacional de Atendimento Socioeducativo.", "Legislação Especial"),
    "l12651": ("Lei 12.651/2012 — Código Florestal", "Institui Código Florestal e normas de proteção à vegetação.", "Legislação Especial"),
    "l12690": ("Lei 12.690/2012 — Sociedades cooperativas", "Altera normas sobre sociedades cooperativas de trabalho.", "Civil e Trabalho"),
    "l12694": ("Lei 12.694/2012 — Simplificação tributária", "Altera normas tributárias e simplifica obrigações acessórias.", "Legislação Especial"),
    "l12714": ("Lei 12.714/2012 — Interoperabilidade", "Institui sistema nacional de interoperabilidade de bases de dados.", "Legislação Especial"),
    "l12737": ("Lei 12.737/2012 — Crimes informáticos", "Tipifica crimes informáticos (Lei Azeredo).", "Penal e Processual"),
    "l12830": ("Lei 12.830/2013 — Investigação criminal", "Dispõe sobre investigação criminal conduzida pelo delegado.", "Penal e Processual"),
    "l12846": ("Lei 12.846/2013 — Anticorrupção empresarial", "Regula responsabilização de empresas por atos contra a administração.", "Constituição e Adm."),
    "l12850": ("Lei 12.850/2013 — Organização criminosa", "Define organização criminosa e instrumentos de investigação.", "Penal e Processual"),
    "l12852": ("Lei 12.852/2013 — Estatuto da Juventude", "Institui Estatuto da Juventude e direitos de jovens.", "Legislação Especial"),
    "l12965": ("Lei 12.965/2014 — Marco Civil da Internet", "Estabelece princípios e garantias do uso da internet.", "Legislação Especial"),
    "l12984": ("Lei 12.984/2014 — HIV/AIDS", "Criminaliza discriminação de portadores de HIV/AIDS.", "Penal e Processual"),
    "l13060": ("Lei 13.060/2014 — Uso da força", "Disciplina uso de instrumentos de menor potencial ofensivo por agentes.", "Penal e Processual"),
    "l13105": ("Lei 13.105/2015 — Código de Processo Civil", "Estabelece normas do Código de Processo Civil.", "Civil e Trabalho"),
    "l13140": ("Lei 13.140/2015 — Mediação", "Dispõe sobre mediação entre particulares como meio de solução de conflitos.", "Civil e Trabalho"),
    "l13146": ("Lei 13.146/2015 — Estatuto da Pessoa com Deficiência", "Institui Lei Brasileira de Inclusão da Pessoa com Deficiência.", "Legislação Especial"),
    "l13188": ("Lei 13.188/2015 — Reintegração de posse", "Altera normas sobre reintegração de posse e usucapião especial.", "Civil e Trabalho"),
    "l13260": ("Lei 13.260/2016 — Terrorismo", "Regula terrorismo e organizações terroristas.", "Penal e Processual"),
    "l13271": ("Lei 13.271/2016 — Improbidade", "Altera dispositivos da Lei de Improbidade Administrativa.", "Constituição e Adm."),
    "l13294": ("Lei 13.294/2016 — Sistema Financeiro", "Altera normas sobre instituições do Sistema Financeiro Nacional.", "Legislação Especial"),
    "l13300": ("Lei 13.300/2016 — Mandado de Injunção", "Regula o mandado de injunção e o mandado de segurança coletivo.", "Constituição e Adm."),
    "l13303": ("Lei 13.303/2016 — Estatuto jurídico de estatais", "Regime jurídico de empresas estatais e sociedades de economia mista.", "Legislação Especial"),
    "l13344": ("Lei 13.344/2016 — Tráfico de pessoas", "Tipifica tráfico de pessoas e medidas de prevenção.", "Penal e Processual"),
    "l13445": ("Lei 13.445/2017 — Migração", "Regula direitos e deveres de migrantes e refugiados.", "Constituição e Adm."),
    "l13455": ("Lei 13.455/2017 — Regularização fundiária", "Altera normas de regularização fundiária urbana e rural.", "Legislação Especial"),
    "l13460": ("Lei 13.460/2017 — Defesa do usuário de serviço público", "Estabelece normas de participação e defesa de usuários de serviços públicos.", "Constituição e Adm."),
    "l13709": ("Lei 13.709/2018 — LGPD", "Regula tratamento de dados pessoais.", "Legislação Especial"),
    "l13775": ("Lei 13.775/2018 — Duplicata eletrônica", "Dispõe sobre emissão de duplicata em formato eletrônico.", "Civil e Trabalho"),
    "l13869": ("Lei 13.869/2019 — Abuso de autoridade", "Altera normas sobre abuso de autoridade e responsabilização.", "Penal e Processual"),
    "l13874": ("Lei 13.874/2019 — Liberdade econômica", "Estabelece Declaração de Direitos de Liberdade Econômica.", "Legislação Especial"),
    "l13966": ("Lei 13.966/2019 — Agências reguladoras", "Altera normas sobre agências reguladoras e servidores.", "Legislação Especial"),
    "l14010": ("Lei 14.010/2020 — Pandemia", "Altera normas sobre prazos processuais e medidas emergenciais.", "Penal e Processual"),
    "l14133": ("Lei 14.133/2021 — Nova Lei de Licitações", "Regula licitações e contratos administrativos.", "Legislação Especial"),
    "l14344": ("Lei 14.344/2022 — Violência doméstica ampliada", "Altera Lei Maria da Penha e tipifica violência doméstica ampliada.", "Penal e Processual"),
    "l14457": ("Lei 14.457/2022 — Assédio no trabalho", "Altera CLT sobre assédio sexual e programas de prevenção.", "Civil e Trabalho"),
    "l14597": ("Lei 14.597/2023 — Acordo de leniência", "Altera normas sobre acordo de leniência e compliance.", "Constituição e Adm."),
    "l14717": ("Lei 14.717/2023 — Crimes financeiros", "Altera normas penais sobre crimes financeiros e criptoativos.", "Penal e Processual"),
    "l14852": ("Lei 14.852/2024 — Programa de integridade", "Altera normas sobre programas de integridade e anticorrupção.", "Constituição e Adm."),
    "l14965": ("Lei 14.965/2024 — Concursos públicos", "Dispõe sobre normas gerais relativas a concursos públicos.", "Constituição e Adm."),
    "l15040": ("Lei 15.040/2024 — Lei do Contrato de Seguro", "Dispõe sobre normas de seguro privado e revoga dispositivos do Código Civil e do DL 73/1966.", "Legislação Especial"),
    "lcp64": ("Lei Complementar 64/1990 — Inelegibilidades", "Estabelece casos de inelegibilidade para cargos eletivos.", "Constituição e Adm."),
    "lcp76": ("Lei Complementar 76/1993 — Fundeb", "Institui Fundo de Manutenção e Desenvolvimento da Educação Básica.", "Legislação Especial"),
    "lcp101": ("Lei Complementar 101/2000 — LRF", "Estabelece responsabilidade fiscal e limites de gastos públicos.", "Constituição e Adm."),
    "lcp105": ("Lei Complementar 105/2001 — Sigilo bancário", "Regula sigilo de operações de instituições financeiras.", "Legislação Especial"),
    "lcp123": ("Lei Complementar 123/2006 — Simples Nacional", "Institui Estatuto Nacional da Microempresa e EPP.", "Legislação Especial"),
    "lcp142": ("Lei Complementar 142/2013 — Previdência complementar", "Regula previdência complementar fechada e aberta.", "Legislação Especial"),
    "lcp146": ("Lei Complementar 146/2013 — PIS/COFINS monofásico", "Altera normas tributárias sobre PIS/COFINS.", "Legislação Especial"),
    "lcp150": ("Lei Complementar 150/2015 — ISS", "Regula ISS sobre serviços de qualquer natureza.", "Legislação Especial"),
    "lcp152": ("Lei Complementar 152/2015 — Orçamento público", "Altera normas sobre orçamento e finanças públicas.", "Legislação Especial"),
    "lcp182": ("Lei Complementar 182/2021 — Recuperação fiscal", "Institui regime de recuperação fiscal de estados e municípios.", "Legislação Especial"),
    "lcp199": ("Lei Complementar 199/2023 — RCU", "Institui Registro Cadastral Unificado de contribuintes.", "Legislação Especial"),
    "numero=556": ("Lei 556/1948 — Crimes contra a economia", "Define crimes contra a economia popular e ordem econômica.", "Penal e Processual"),
}

EMC_KNOWN: dict[str, tuple[str, str]] = {
    "emc02": ("EC 2/1965", "Institui o Parlamento e altera dispositivos constitucionais."),
    "emc03": ("EC 3/1993", "Altera prazo de mandato de presidentes de tribunais."),
    "emc08": ("EC 8/1995", "Altera normas sobre aposentadoria de servidores públicos."),
    "emc17": ("EC 17/1965", "Altera dispositivos sobre organização do Poder Judiciário."),
    "emc45": ("EC 45/2004", "Reforma do Judiciário: súmula vinculante, competências e quarentena."),
    "emc54": ("EC 54/2007", "Institui o Regime de Recuperação Fiscal."),
    "emc91": ("EC 91/2016", "Altera normas sobre aposentadoria e regime previdenciário."),
    "emc103": ("EC 103/2019 — Reforma da Previdência", "Reforma previdenciária e regras de transição."),
    "emc106": ("EC 106/2020", "Institui regime extraordinário fiscal e financeiro (pandemia)."),
    "emc111": ("EC 111/2021", "Altera normas sobre precatórios e pagamentos judiciais."),
    "emc113": ("EC 113/2021", "Altera normas sobre precatórios e emendas constitucionais."),
    "emc114": ("EC 114/2021", "Altera normas sobre precatórios e pagamentos de sentenças."),
    "emc117": ("EC 117/2022", "Altera normas sobre precatórios e emendas parlamentares."),
    "emc123": ("EC 123/2022", "Altera normas sobre precatórios e pagamentos judiciais."),
    "emc125": ("EC 125/2022", "Altera normas sobre precatórios e emendas de relator."),
    "emc127": ("EC 127/2022", "Altera normas sobre precatórios e pagamentos de débitos."),
    "emc132": ("EC 132/2023 — Reforma Tributária", "Altera o Sistema Tributário Nacional e institui IBS/CBS."),
    "emc133": ("EC 133/2024", "Altera normas sobre mandato e aposentadoria de ministros."),
}


def legis_slug_from_url(url: str) -> str | None:
    m = re.search(
        r"/(lcp|del|emc|d|l)(\d[\d.]*?)(?:consolidado|consol|compilada|comp|cons|orig|_)?\.htm",
        url.lower(),
    )
    if not m:
        return None
    prefix, digits = m.group(1), m.group(2).replace(".", "")
    return f"{prefix}{digits}"


def match_key(url: str) -> str | None:
    slug = legis_slug_from_url(url)
    if slug and slug in KNOWN:
        return slug
    if slug and slug.replace("l0", "l", 1) in KNOWN:
        return slug.replace("l0", "l", 1)
    u = url.lower()
    for key in sorted(KNOWN.keys(), key=len, reverse=True):
        if key.lower() in u:
            return key
    for key in EMC_KNOWN:
        if key in u:
            return key
    return None


def build_entries() -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for key, (titulo, resumo, secao) in KNOWN.items():
        entries[key] = {"titulo": titulo, "resumo": resumo, "secao": secao}
    for key, (titulo, resumo) in EMC_KNOWN.items():
        entries[key] = {"titulo": titulo, "resumo": resumo, "secao": "Constituição e Adm."}
    return entries


def patch_catalog(entries: dict[str, dict[str, str]]) -> None:
    if not CATALOG.exists():
        return
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    changed = 0
    for doc in data.get("documents", []):
        url = doc.get("url") or ""
        key = match_key(url)
        if not key or key not in entries:
            continue
        meta = entries[key]
        titulo = meta.get("titulo")
        if titulo:
            doc["title"] = titulo
            doc.setdefault("meta", {})["titulo"] = titulo
            changed += 1
        if meta.get("secao"):
            doc.setdefault("meta", {})["secao_lei_seca"] = meta["secao"]
            doc.setdefault("organized", {})["secao_lei_seca"] = meta["secao"]
        if meta.get("resumo"):
            doc["resumo"] = meta["resumo"]
    if changed:
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Patched {changed} titles in {CATALOG}")


def patch_bodies(entries: dict[str, dict[str, str]]) -> None:
    if not BODIES.exists():
        return
    data = json.loads(BODIES.read_text(encoding="utf-8"))
    bodies = data.get("bodies") or {}
    changed = 0
    for url, body in list(bodies.items()):
        key = match_key(url)
        if not key or key not in entries:
            continue
        titulo = entries[key].get("titulo")
        if not titulo or not isinstance(body, str):
            continue
        lines = body.split("\n", 2)
        if lines and lines[0].startswith("# "):
            new_first = f"# {titulo}"
            if lines[0] != new_first:
                lines[0] = new_first
                bodies[url] = "\n".join(lines)
                changed += 1
    if changed:
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        BODIES.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"Patched {changed} headers in {BODIES}")


def patch_summaries(entries: dict[str, dict[str, str]]) -> None:
    data = json.loads(SUMMARIES.read_text(encoding="utf-8"))
    for item in data.get("list", []):
        url = item.get("url") or ""
        key = match_key(url)
        if not key or key not in entries:
            continue
        meta = entries[key]
        if meta.get("titulo"):
            item["titulo"] = meta["titulo"]
        if meta.get("resumo"):
            item["resumo"] = meta["resumo"]
        if meta.get("secao"):
            item["secao"] = meta["secao"]
        path_key = url.split("planalto.gov.br")[-1].split("senado.leg.br")[-1].lower().split("?")[0].rstrip("/")
        data["summaries"][path_key] = {
            "titulo": item["titulo"],
            "resumo": item.get("resumo", ""),
            "secao": item.get("secao", ""),
            "url": url,
        }
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data["count"] = len(data.get("list", []))
    SUMMARIES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    entries = build_entries()
    OUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(entries),
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    patch_summaries(entries)
    patch_catalog(entries)
    patch_bodies(entries)
    print(f"Wrote {len(entries)} known entries -> {OUT}")
    print(f"Patched {SUMMARIES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
