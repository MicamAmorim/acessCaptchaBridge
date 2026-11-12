# Histórico de versões

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
