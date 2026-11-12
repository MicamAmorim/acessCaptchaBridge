# AcessoPonte — extensão de acessibilidade com seletor de modelos (v0.2.0)

Extensão Chrome/Edge Manifest V3 + ponte Python para análise visual de interfaces, com seleção dinâmica dos modelos visuais que **estão instalados no Ollama** e dos modelos visuais **anunciados pelo Codex CLI instalado e configurado no PC**.

**Escopo:** identificar recursos oficiais de áudio, acessibilidade, suporte e navegação por teclado. O projeto não responde CAPTCHAs, não automatiza verificações de segurança nem simula atividade humana.

## O que mudou na v0.2

- Seletor `Modelo disponível` na tela principal da extensão, com grupos de provedores distintos.
- Ollama só aparece quando o serviço local responde e há pelo menos um **modelo instalado** que expõe capacidade `vision` (`/api/tags` + `/api/show`). Modelos somente de texto não são exibidos.
- Codex só aparece quando o comando **`codex`** está no `PATH` e `codex app-server` responde a `model/list` com modelos que aceitam imagens. A detecção usa a configuração e autenticação locais do Codex, sem instalar nada.
- A lista de modelos Codex é o **catálogo retornado** pelo Codex para a configuração corrente; a disponibilidade real por conta/permissão é confirmada apenas ao executar uma análise. Os modelos de Codex **não são baixados no PC** como os do Ollama.
- Se nenhum provedor estiver utilizável, o seletor fica oculto, e uma orientação explica o motivo.
- Seleção salva automaticamente (`provider` + `model`) e botão para atualizar a lista quando instalar, remover ou configurar modelos.
- A captura com Codex exige autorização adicional, pois o CLI pode encaminhar imagens a servidores externos, dependendo da configuração. **O Codex com modelo remoto não é inferência local.**
- O backend verifica novamente a combinação provedor/modelo escolhida antes de processar.

## Requisitos

- Windows 10/11, Python 3.10+ (somente biblioteca padrão).
- Chrome/Edge com extensão descompactada.
- Pelo menos um dos serviços abaixo:
  - **Ollama** instalado, em execução em `127.0.0.1:11434`, com modelo de visão já baixado; ou
  - **Codex CLI** instalado, disponível ao executar `codex` no PowerShell, com provedor e autenticação corretamente configurados. *Apenas ter o app de desktop do Codex instalado não garante que o comando `codex` esteja disponível.*

### Como instalar / atualizar

1. Se quiser Ollama, instale-o e baixe um modelo visual. Exemplo opcional:

   ```powershell
   ollama pull qwen3-vl:4b
   ollama list
   ```

   Não é necessário baixar o modelo acima se você já tem outro VLM compatível.

2. Se quiser Codex, confirme no PowerShell:

   ```powershell
   where.exe codex
   codex --version
   ```

   Faça login e ajuste sua configuração de provedor com os métodos habituais do Codex. O AcessoPonte não lê nem altera credenciais do Codex.

3. Execute `backend/iniciar-windows.bat`. Mantenha a janela aberta e copie o **token** apresentado. O token persistente fica no arquivo `backend/.access_token`, que não deve ser compartilhado.

4. Chrome: `chrome://extensions`, habilite o modo do desenvolvedor e clique em **Carregar sem compactação**, escolhendo **a pasta `extension` deste pacote**. No Edge: `edge://extensions`. Se já estiver usando a versão anterior, substitua os arquivos da pasta usada anteriormente e clique em **Atualizar** no cartão da extensão.

5. Abra o popup do AcessoPonte, expanda **Configurar conexão local**, cole o token e clique em **Salvar configuração**.

6. A lista será consultada automaticamente. O seletor mostrará **somente grupos detectados**, sem precisar digitar o nome de um modelo. Ao instalar/remover um modelo ou iniciar o Ollama, use **Atualizar modelos detectados**.

7. Para teste sem acessar qualquer processo real, execute:

   ```powershell
   cd demo
   py -m http.server 8080 --bind 127.0.0.1
   ```

   Abra `http://127.0.0.1:8080/pagina-teste.html`, clique em **Diagnosticar página** e, se quiser, autorize explicitamente a captura para análise visual.

## Funcionamento

```text
 Extensão Chrome/Edge
   ├─ Inspeção limitada DOM/ARIA (sem enviar corpo completo de documentos)
   ├─ Lista de modelos: GET http://127.0.0.1:8765/models + token
   │    ├─ Ollama GET /api/tags, POST /api/show  → somente modelos com visão
   │    └─ Codex app-server, model/list          → modelos com imagens
   ├─ Autorização de captura por análise
   └─ POST /analyze (provider, model, imagem, metadados limitados)
             │
             ├─ Ollama /api/chat em localhost
             └─ Codex CLI `codex exec -i ... -m ...` com sandbox read-only
```

## Privacidade e limitações

- **Ollama:** a imagem não é gravada em disco pelo AcessoPonte; a API é local. Isso não cobre modelos do Ollama que usem provedores remotos configurados: verifique a configuração antes de analisar material sigiloso.
- **Codex:** o AcessoPonte cria uma imagem **temporária em disco**, necessária para o argumento `--image` da CLI, e a remove ao final. O Codex pode enviar a captura ao provedor configurado e pode manter registros próprios conforme suas preferências. O AcessoPonte não controla a política de retenção do provedor remoto.
- O AcessoPonte usa `--sandbox read-only`, `--ask-for-approval never`, `--ephemeral` e um diretório temporário para tarefas Codex, com a instrução de não utilizar ferramentas. Essas opções reduzem riscos, mas **não constituem isolamento perfeito nem auditoria formal dos plugins e ferramentas configurados no Codex**.
- As imagens só são capturadas após consentimento do usuário, e o Codex pede consentimento adicional. Não use com dados processuais ou pessoais confidenciais sem avaliar riscos, sigilo e políticas do órgão.
- A ponte escuta apenas `127.0.0.1:8765` e as rotas sensíveis exigem um token Bearer. Não exponha essa porta à rede externa.
- A lista do Codex mostra o catálogo do app-server configurado. Acesso efetivo ao modelo, limites de conta e suporte real a imagem só podem ser verificados ao executar uma requisição.
- O navegador não permite inspecionar todos os iframes de terceiros com `activeTab` e não expõe toda a árvore de acessibilidade diretamente. O VLM pode errar. O protótipo ainda não foi validado com usuários cegos e NVDA em portais judiciais reais.
- O popup precisa permanecer aberto durante a análise. Não há observação automática de páginas em segundo plano.

## Testes automatizados

Na pasta raiz do projeto:

```powershell
py -m unittest discover -s tests -v
node --check extension/background.js
node --check extension/popup.js
```

Testes incluem: modelos Ollama com e sem visão, ausência de provedor, ausência do Codex, filtros do catálogo, handshake JSONL `app-server` simulado, validação de entrada e seleção de modelo.

## Próximos passos

- Validar a descoberta contra as versões reais do Codex CLI e Ollama no seu Windows.
- Testar com NVDA, teclado e usuários cegos, incluindo mensagens de erro e tempo de inferência.
- Considerar recorte manual de tela e mascaramento de informações sensíveis.
- Adotar trilhas oficiais de acessibilidade de PJe, eproc e demais portais.

Fontes técnicas:

- [Codex app-server: model/list](https://learn.chatgpt.com/docs/app-server)
- [Codex CLI: --image, --model e codex exec](https://learn.chatgpt.com/docs/cli/reference)
- [Ollama API: tags/show](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml)
