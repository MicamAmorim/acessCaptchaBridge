# AcessoPonte — acessCaptchaBridge

Tecnologia assistiva experimental para identificar barreiras de acessibilidade e alternativas oficiais (áudio, navegação por teclado, suporte) em páginas web, usando extensão Chrome/Edge e uma ponte local para modelos visuais Ollama ou Codex.

**Versão:** 0.2.0 (MVP). O sistema não resolve CAPTCHA automaticamente, não contorna mecanismos antirrobôs e não simula interação humana para evasão.

## Instalação

Requisitos: Windows 10/11, Python 3.10+, Chrome/Edge e pelo menos um dos provedores Ollama com VLM instalado ou Codex CLI configurado.

1. Execute `backend/iniciar-windows.bat` e copie o token local exibido.
2. Ative o modo do desenvolvedor em `chrome://extensions` e use **Carregar sem compactação** apontando para `extension/`.
3. No popup, salve o token e atualize a lista de modelos.
4. Para testar, execute `py -m http.server 8080 --bind 127.0.0.1` na pasta `demo/` e abra `http://127.0.0.1:8080/pagina-teste.html`.

## Privacidade

A análise de tela exige autorização explícita. O Ollama pode executar localmente, conforme configuração; o Codex pode encaminhar imagens para um provedor remoto. Não use com dados processuais sigilosos sem análise de riscos e regras da instituição.

## Testes

`python -m unittest discover -s tests -v`

Projeto experimental sem validação com NVDA/usuários cegos em portais judiciais reais.
