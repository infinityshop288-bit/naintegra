"""Universo de acoes acompanhadas + config setorial p/ analise automatizada.

Cada acao tem setor, raiz de opcao (B3) e "tilt" macro: como o setor tende a
reagir a variacoes de Selic, dolar, Ibovespa e preco de commodities. Valores em
[-1..+1] (sinal do efeito). Usado para compor o vies automatizado.
"""
from __future__ import annotations

# tilt: reacao do setor a ALTA de cada fator macro
#   selic_up: alta de juros | usd_up: dolar subindo | ibov_up: bolsa subindo
#   commodity_up: alta de commodities globais (petroleo/minerio)
SECTOR_TILT = {
    "Óleo & Gás":       {"selic_up": -0.2, "usd_up": +0.8, "ibov_up": +0.4, "commodity_up": +0.9},
    "Varejo":           {"selic_up": -0.9, "usd_up": -0.3, "ibov_up": +0.7, "commodity_up": -0.1},
    "Energia elétrica": {"selic_up": -0.3, "usd_up": -0.1, "ibov_up": +0.3, "commodity_up": +0.0},
    "Bancos":           {"selic_up": +0.4, "usd_up": -0.1, "ibov_up": +0.7, "commodity_up": +0.1},
    "Seguradora":       {"selic_up": +0.5, "usd_up": -0.1, "ibov_up": +0.4, "commodity_up": +0.0},
    "Commodities":      {"selic_up": -0.2, "usd_up": +0.7, "ibov_up": +0.5, "commodity_up": +0.9},
    "Alimentação":      {"selic_up": -0.3, "usd_up": +0.3, "ibov_up": +0.3, "commodity_up": +0.2},
    "Construção civil": {"selic_up": -0.9, "usd_up": -0.2, "ibov_up": +0.7, "commodity_up": -0.2},
    "Bens de capital":  {"selic_up": -0.3, "usd_up": +0.6, "ibov_up": +0.5, "commodity_up": -0.2},
    "Siderurgia":       {"selic_up": -0.4, "usd_up": +0.6, "ibov_up": +0.5, "commodity_up": +0.8},
}

# ticker -> (nome, setor, raiz de opcao)
UNIVERSE = {
    "PRIO3": ("Prio S.A.",          "Óleo & Gás",       "PRIO"),
    "BRAV3": ("Brava Energia",      "Óleo & Gás",       "BRAV"),
    "MGLU3": ("Magazine Luiza",     "Varejo",           "MGLU"),
    "LREN3": ("Lojas Renner",       "Varejo",           "LREN"),
    "EQTL3": ("Equatorial Energia", "Energia elétrica", "EQTL"),
    "CMIG4": ("Cemig",              "Energia elétrica", "CMIG"),
    "ITUB4": ("Itaú Unibanco",      "Bancos",           "ITUB"),
    "BBDC4": ("Bradesco",           "Bancos",           "BBDC"),
    "BBAS3": ("Banco do Brasil",    "Bancos",           "BBAS"),
    "BBSE3": ("BB Seguridade",      "Seguradora",       "BBSE"),
    "PSSA3": ("Porto Seguro",       "Seguradora",       "PSSA"),
    "VALE3": ("Vale",               "Commodities",      "VALE"),
    "SUZB3": ("Suzano",             "Commodities",      "SUZB"),
    "ABEV3": ("Ambev",              "Alimentação",      "ABEV"),
    "MBRF3": ("MBRF (Marfrig+BRF)", "Alimentação",      "MBRF"),
    "CYRE3": ("Cyrela",             "Construção civil", "CYRE"),
    "MRVE3": ("MRV Engenharia",     "Construção civil", "MRVE"),
    "DIRR3": ("Direcional",         "Construção civil", "DIRR"),
    "CURY3": ("Cury Construtora",   "Construção civil", "CURY"),
    "WEGE3": ("WEG",                "Bens de capital",  "WEGE"),
    "CSNA3": ("CSN (Sid. Nacional)","Siderurgia",       "CSNA"),
}

TICKERS = list(UNIVERSE)


def yahoo_symbol(t: str) -> str:
    return t + ".SA"
