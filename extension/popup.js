'use strict';
const $ = id => document.getElementById(id);
const API = 'http://127.0.0.1:8765';
let lastScan = null;
let lastDescription = '';
let available = [];
let isWorking = false;

function message(text, isError = false) {
  $('message').textContent = text;
  $('message').style.color = isError ? '#a31515' : '#105b45';
}
function updateActions() {
  const value = $('model').value;
  const chosen = available.find(m => `${m.provider}::${m.id}` === value);
  $('codexConsentRow').hidden = chosen?.provider !== 'codex';
  $('analyze').disabled = isWorking || !chosen || !$('consent').checked ||
    (chosen.provider === 'codex' && !$('codexConsent').checked);
}
function call(type, extra = {}) {
  return new Promise((resolve, reject) => chrome.runtime.sendMessage({ type, ...extra }, response => {
    if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
    if (!response?.ok) return reject(new Error(response?.error || 'Falha na comunicação.'));
    resolve(response.data);
  }));
}
async function busy(button, work) {
  isWorking = true;
  button.disabled = true;
  const previous = button.textContent;
  button.textContent = 'Processando…';
  message('');
  try { await work(); }
  catch (error) { message(error.message || String(error), true); }
  finally { button.textContent = previous; isWorking = false; button.disabled = false; updateActions(); }
}
function renderScan(scan) {
  lastScan = scan;
  $('scanResults').hidden = false;
  const providers = [...new Set(scan.widgets.map(w => w.iframeHost).filter(Boolean))].join(', ');
  $('summary').textContent = `${scan.framesInspected} quadro(s) examinados; ${scan.widgets.length} possível(is) elemento(s) de verificação; ${scan.controls.length} controle(s) de acessibilidade. ` +
    (providers ? `Serviços identificados: ${providers}.` : 'Nenhum provedor identificado na estrutura acessível.');
  const area = $('controls');
  area.replaceChildren();
  if (!scan.controls.length) {
    const p = document.createElement('p');
    p.textContent = 'Nenhum controle de áudio ou acessibilidade foi identificado no conteúdo inspecionável. Tente a análise visual ou procure atendimento acessível do portal.';
    area.append(p);
    return;
  }
  scan.controls.forEach((control, number) => {
    const item = document.createElement('div');
    item.className = 'control';
    const label = document.createElement('p');
    label.textContent = `${number + 1}. ${control.kind === 'audio' ? 'Áudio' : 'Acessibilidade'}: ${control.label}`;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `Focar controle ${number + 1}`;
    button.setAttribute('aria-label', `Focar ${control.label} na página`);
    button.addEventListener('click', () => busy(button, async () => {
      const outcome = await call('FOCUS', { control });
      if (!outcome.ok) throw new Error(outcome.reason || 'Não foi possível focar.');
      message('Controle selecionado. Retorne à página e pressione Enter ou Espaço.');
    }));
    item.append(label, button); area.append(item);
  });
}
async function localFetch(path, opts = {}) {
  const token = $('token').value.trim();
  if (token.length < 20) throw new Error('Configure primeiro o token exibido pelo servidor local.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeout || 180_000);
  try {
    const response = await fetch(`${API}${path}`, {
      ...opts,
      headers: { 'Authorization': `Bearer ${token}`, ...(opts.headers || {}) },
      signal: controller.signal
    });
    const json = await response.json();
    if (!response.ok) throw new Error(json.error || `Erro HTTP ${response.status}.`);
    return json;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Tempo esgotado. Verifique o serviço local e tente novamente.');
    throw error;
  } finally { clearTimeout(timer); }
}
async function refreshModels(saved = null) {
  $('modelChooser').hidden = true;
  $('modelStatus').textContent = 'Consultando Ollama e Codex instalados…';
  available = [];
  updateActions();
  try {
    const data = await localFetch('/models', { timeout: 35_000 });
    available = Array.isArray(data.models) ? data.models.filter(m =>
      ['ollama', 'codex'].includes(m.provider) && typeof m.id === 'string') : [];
    const selected = saved || await chrome.storage.local.get(['provider', 'model']);
    const select = $('model');
    select.replaceChildren();
    for (const provider of ['ollama', 'codex']) {
      const models = available.filter(m => m.provider === provider);
      if (!models.length) continue;
      const group = document.createElement('optgroup');
      group.label = provider === 'ollama' ? 'Ollama — instalado e visual' : 'Codex CLI — catálogo acessível';
      for (const model of models) {
        const option = document.createElement('option');
        option.value = `${provider}::${model.id}`;
        option.textContent = model.label || model.id;
        group.appendChild(option);
      }
      select.appendChild(group);
    }
    if (!available.length) {
      $('modelStatus').textContent = 'Nenhum modelo visual detectado. Inicie o Ollama com um modelo de visão instalado ou configure o Codex CLI.';
      return;
    }
    const preferred = `${selected.provider}::${selected.model}`;
    select.value = available.some(m => `${m.provider}::${m.id}` === preferred)
      ? preferred : `${available[0].provider}::${available[0].id}`;
    $('modelChooser').hidden = false;
    const ollamaCount = available.filter(m => m.provider === 'ollama').length;
    const codexCount = available.filter(m => m.provider === 'codex').length;
    $('modelStatus').textContent = `${ollamaCount} modelo(s) visuais no Ollama; ${codexCount} modelo(s) visuais no catálogo Codex. O acesso à conta Codex será confirmado durante o uso.`;
    await saveModel();
  } catch (error) {
    $('modelStatus').textContent = 'Não foi possível consultar modelos: ' + (error.message || String(error));
  } finally { updateActions(); }
}
async function saveModel() {
  const chosen = available.find(m => `${m.provider}::${m.id}` === $('model').value);
  if (!chosen) return;
  await chrome.storage.local.set({ provider: chosen.provider, model: chosen.id });
  $('codexConsent').checked = false; // Reconfirm when switching to remote-capable provider.
  updateActions();
}
async function init() {
  const saved = await chrome.storage.local.get(['token', 'provider', 'model']);
  $('token').value = saved.token || '';
  $('save').addEventListener('click', () => busy($('save'), async () => {
    const token = $('token').value.trim();
    if (token.length < 20) throw new Error('O token deve ter pelo menos 20 caracteres.');
    await chrome.storage.local.set({ token });
    await refreshModels();
    message('Conexão configurada. A lista de modelos foi atualizada.');
  }));
  $('model').addEventListener('change', () => { saveModel().catch(error => message(error.message, true)); });
  $('refreshModels').addEventListener('click', () => busy($('refreshModels'), async () => { await refreshModels(); }));
  $('consent').addEventListener('change', updateActions);
  $('codexConsent').addEventListener('change', updateActions);
  $('scan').addEventListener('click', () => busy($('scan'), async () => {
    renderScan(await call('SCAN'));
    message('Diagnóstico concluído.');
  }));
  $('analyze').addEventListener('click', () => busy($('analyze'), async () => {
    if (!$('consent').checked) throw new Error('Autorize a captura antes de prosseguir.');
    const selected = available.find(m => `${m.provider}::${m.id}` === $('model').value);
    if (!selected) throw new Error('Escolha um modelo detectado.');
    if (selected.provider === 'codex' && !$('codexConsent').checked)
      throw new Error('Confirme a autorização de processamento com Codex.');
    const shot = await call('CAPTURE');
    const data = await localFetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image: shot.image, scan: shot.scan, model: selected.id, provider: selected.provider,
        confirmRemote: selected.provider === 'codex' && $('codexConsent').checked
      })
    });
    lastDescription = data.description || '';
    $('modelText').textContent = lastDescription || 'O modelo não forneceu uma descrição.';
    $('modelResults').hidden = false;
    if (data.scan) renderScan(data.scan);
    message(`Análise concluída com ${data.provider} / ${data.model}.`);
  }));
  $('copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(lastDescription); message('Descrição copiada.'); }
    catch (_) { message('Não foi possível copiar a descrição.', true); }
  });
  updateActions();
  try {
    await call('HEALTH');
    $('server').textContent = 'Servidor local conectado.';
    if ($('token').value.trim().length >= 20) await refreshModels(saved);
  } catch (_) { $('server').textContent = 'Serviço local indisponível. Execute backend/iniciar-windows.bat.'; }
}
init().catch(error => message(error.message, true));
