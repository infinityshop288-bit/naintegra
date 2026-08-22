# App Store — resposta à rejeição (NaIntegra Lex)

A versão 1.0.1 foi rejeitada nas guidelines **2.1.0**, **2.3.10**, **3.1.1**, **4.0.0** e **5.1.1**.
A estratégia adotada foi **tornar o app gratuito**, o que elimina a causa raiz (3.1.1) e simplifica
as demais.

## O que mudou no produto

| Antes | Agora |
|-------|-------|
| Assinatura obrigatória (R$ 19,90/mês, R$ 199,90/ano) | **Gratuito**, sem nenhuma cobrança |
| Checkout Mercado Pago no iOS (pagamento externo) | Removido do código |
| `cordova-plugin-purchase` (StoreKit) no projeto iOS | Plugin desinstalado; não há mais SDK de compras no binário |
| Login obrigatório para ver o acervo | Login **opcional**, só para sincronizar |
| Política de privacidade apontando para a tela de contato | Página dedicada: `web/lex/privacidade.html` |

## Como cada rejeição foi endereçada

### 3.1.1 — Payments: In-App Purchase
O app não tem mais nenhum mecanismo de pagamento. Não há assinatura, paywall, botão "Assinar",
tela de checkout, nem link para processador externo. Nenhum produto de In-App Purchase precisa
ser criado — os IAPs `lex_mensal` e `lex_anual` **não devem** ser enviados para revisão.

Se existirem produtos em estado "Missing Metadata" ou "Waiting for Review" no App Store Connect,
remova-os da versão (ou marque como "Removed from Sale") antes de reenviar.

### 2.1.0 — App Completeness
O revisor antes não conseguia passar do paywall. Agora, ao abrir o app, todo o conteúdo já está
acessível sem login. Em **Informações para revisão**, desmarque **"Sign-in required"**.

### 2.3.10 — Accurate Metadata
Descrição e capturas foram revisadas: não mencionam mais assinatura ou preço. A descrição declara
explicitamente que o app é gratuito, sem compras e sem anúncios. Textos em `store-assets/app-store.md`.

### 4.0.0 — Design
Removida a landing page comercial que era exibida como tela inicial. A home agora abre direto no
painel do acervo (Lei Seca, Jurisprudência, Flashcards, Questões, Plano de estudos, Favoritos),
seguindo o padrão de um app de conteúdo.

### 5.1.1 — Privacy: Data Collection and Storage
- Política de privacidade dedicada e específica do app:
  https://www.naintegracursos.com.br/lex/privacidade.html
- O app funciona sem coletar dado algum (uso sem conta).
- Exclusão de conta disponível dentro do app: `#/excluir-conta`.
- Os rótulos de privacidade no App Store Connect devem declarar **apenas** e-mail e conteúdo do
  usuário, ambos opcionais e não usados para rastreamento. **Não** declarar dados de pagamento.

## Checklist antes de reenviar

- [ ] Web atualizado publicado em `https://www.naintegracursos.com.br/lex/` (o app carrega o conteúdo remoto)
- [ ] `privacidade.html` acessível publicamente
- [ ] Nenhum IAP anexado à versão
- [ ] "Sign-in required" desmarcado
- [ ] Descrição e notas do revisor atualizadas (`store-assets/app-store.md`)
- [ ] Rótulos de privacidade sem dados financeiros
- [ ] Build 1.1.0 (6) processado e vinculado à versão
- [ ] Notas da versão: `store-assets/release-notes-pt-BR.txt`

## Supabase

As edge functions de pagamento foram removidas do repositório
(`lex-subscription-checkout`, `lex-subscription-confirm`, `lex-apple-iap-verify`).
Se ainda estiverem implantadas no projeto, remova-as:

```bash
supabase functions delete lex-subscription-checkout
supabase functions delete lex-subscription-confirm
supabase functions delete lex-apple-iap-verify
```

A função `lex-delete-account` permanece — é ela que atende ao requisito de exclusão de conta.

## Build iOS

```bash
cd mobile && npm run build && npm run archive:ios
```
