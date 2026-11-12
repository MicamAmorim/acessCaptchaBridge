# Histórico de versões

## v0.3.0 — painel lateral e permissões persistentes

- Migração do popup para `chrome.sidePanel` com permanência durante navegação e atalho `Alt+Shift+A`.
- Captura e inspeção somente sob comando do usuário, com autorização opcional persistente `<all_urls>` do navegador; revogação pelo próprio painel.
- Consentimento Codex salvo por origem (site) para evitar confirmações repetidas, com revogação independente.
- Seção de permissões recolhível e aberta apenas quando faltar acesso; mensagens de estado mais concisas para tecnologias assistivas.
- Reconexão automática do painel quando o backend voltar, mantendo token e modelo.
- Proteção adicional contra captura de guia diferente daquela inspecionada.
- Quatro testes de regressão específicos da experiência de barra lateral; uso real com NVDA e Edge ainda requer validação.

## Hotfix — Codificação UTF-8 no Windows (main)

- Codex CLI exige UTF-8 para o prompt recebido em `stdin`. O backend agora envia bytes de `instruction.encode('utf-8')`, sem depender da página de códigos padrão do Windows.
- Saída de erro capturada como bytes e decodificada explicitamente em UTF-8 (com substituição de caracteres inválidos).
- Novo teste verifica a passagem de bytes UTF-8 com caracteres acentuados em português.
- Atualize com `git pull --ff-only origin main` e reinicie o servidor local. Não é necessário reinstalar a extensão.

## Hotfix — Codex CLI 0.166.x (main)

- Corrigida a chamada `codex exec`: a política de aprovação agora é aplicada pela opção global `-c approval_policy="never"`, evitando o argumento inválido `--ask-for-approval` no subcomando.
- O diagnóstico do Codex agora é mostrado no terminal local, com uma mensagem resumida e sem o stderr bruto na extensão.
- Teste de regressão para os argumentos e os erros do CLI.

## v0.2.0 — MVP de seleção dinâmica

- Extensão Chrome/Edge Manifest V3.
- Detecta modelos com visão instalados no Ollama em `127.0.0.1:11434`.
- Descobre modelos com capacidade visual no catálogo do Codex CLI instalado, via `codex app-server`.
- Oculta provedores indisponíveis, armazena seleção e oferece atualização da lista.
- Exige consentimento por captura, com consentimento adicional para Codex por potencial envio de imagem a serviço remoto.
- Analisa DOM/ARIA e oferece navegação para alternativas oficiais de áudio/acessibilidade sem transpor controles antirrobôs.
- Backend Python local com token de autenticação e API somente em loopback.
- Testes unitários e validação sintática de JavaScript.

**Estado:** protótipo experimental. Resultados simulados não substituem testes reais com Codex, Ollama, Chrome/Edge, NVDA e portais de justiça.
