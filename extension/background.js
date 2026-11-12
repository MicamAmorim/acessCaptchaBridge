'use strict';

const SERVICE_URL = 'http://127.0.0.1:8765';

// Keep the interface open when the user clicks back into the page.
// No background scans or screenshots are started by this registration.
async function enableSidePanel() {
  if (chrome.sidePanel?.setPanelBehavior) {
    try { await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }); }
    catch (error) { console.warn('AcessoPonte: não foi possível habilitar o painel lateral:', error.message); }
  }
}
chrome.runtime.onInstalled.addListener(enableSidePanel);
chrome.runtime.onStartup.addListener(enableSidePanel);
void enableSidePanel();

async function requirePersistentAccess() {
  const allowed = await chrome.permissions.contains({ origins: ['<all_urls>'] });
  if (!allowed) throw new Error('Autorize uma vez o acesso persistente na seção Permissões do painel lateral.');
}

// Executed within each accessible page frame. Captures a restricted set of
// accessibility-related controls; does not read forms, cookies or page bodies.
function inspectPageFrame() {
  const compact = (s) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, 140);
  const text = (el) => compact(el.getAttribute('aria-label') ||
    el.getAttribute('title') || el.getAttribute('alt') ||
    el.innerText || el.textContent || el.value || '');
  const isVisible = (el) => {
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' &&
      rect.width > 0 && rect.height > 0;
  };
  const classify = (label) => {
    const s = label.toLowerCase();
    if (/(?:^|[^a-zà-ÿ0-9])(audio|sound|listen|hear|spoken|ouvir|áudio|som|voz|escutar|escuche|sonido)(?:$|[^a-zà-ÿ0-9])/i.test(s)) return 'audio';
    if (/acessibilidade|accessibility|accesibilidad|defici[eê]ncia visual|visual impairment|screen reader|leitor de tela|accessible|recurso acess[ií]vel/i.test(s)) return 'accessibility';
    return null;
  };
  const capRegex = /captcha|recaptcha|hcaptcha|turnstile|verific[aá][cç][aã]o humana|i['’]?m not a robot|n[aã]o sou um rob[oô]|human verification/i;
  const controls = [];
  const all = [...document.querySelectorAll('button, a[href], input[type="button"], input[type="submit"], [role="button"]')].slice(0, 600);
  all.forEach((el, index) => {
    if (!isVisible(el)) return;
    const label = text(el);
    const kind = classify(label);
    if (!kind) return;
    controls.push({ index, kind, label: label || kind, tag: el.tagName.toLowerCase() });
  });
  const widgets = [...document.querySelectorAll('iframe, [id], [class]')]
    .filter(el => {
      const marker = `${el.tagName} ${el.id || ''} ${typeof el.className === 'string' ? el.className : ''} ` +
        (el.tagName === 'IFRAME' ? (el.getAttribute('title') || '') + ' ' + (el.getAttribute('src') || '').split('?')[0] : '');
      return capRegex.test(marker);
    })
    .slice(0, 25)
    .map(el => {
      const src = el.tagName === 'IFRAME' ? (el.getAttribute('src') || '') : '';
      let host = '';
      try { host = src ? new URL(src, document.baseURI).hostname : ''; } catch (_) {}
      return {
        element: el.tagName.toLowerCase(),
        hint: compact(el.getAttribute('title') || el.id || (typeof el.className === 'string' ? el.className : '')),
        iframeHost: host
      };
    });
  return {
    frameTitle: compact(document.title),
    isLikelyChallenge: widgets.length > 0 || capRegex.test(compact(document.title)),
    widgets,
    controls: controls.slice(0, 35)
  };
}

// Only focuses a semantically identified accessibility control selected by the
// user. It never submits answers or generates human-like automation patterns.
function focusControl(index, expectedKind, expectedLabel) {
  const compact = s => String(s || '').replace(/\s+/g, ' ').trim().slice(0, 140);
  const isVisible = el => {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };
  const classify = label => {
    const s = label.toLowerCase();
    if (/(?:^|[^a-zà-ÿ0-9])(audio|sound|listen|hear|spoken|ouvir|áudio|som|voz|escutar|escuche|sonido)(?:$|[^a-zà-ÿ0-9])/i.test(s)) return 'audio';
    if (/acessibilidade|accessibility|accesibilidad|defici[eê]ncia visual|visual impairment|screen reader|leitor de tela|accessible|recurso acess[ií]vel/i.test(s)) return 'accessibility';
    return null;
  };
  const all = [...document.querySelectorAll('button, a[href], input[type="button"], input[type="submit"], [role="button"]')].slice(0, 600);
  const el = all[index];
  if (!el || !isVisible(el)) return { ok: false, reason: 'Controle não está mais visível.' };
  const label = compact(el.getAttribute('aria-label') || el.getAttribute('title') ||
    el.getAttribute('alt') || el.innerText || el.textContent || el.value || '');
  if (label !== expectedLabel || classify(label) !== expectedKind || !['audio', 'accessibility'].includes(expectedKind)) {
    return { ok: false, reason: 'A página mudou. Execute novo diagnóstico.' };
  }
  el.scrollIntoView({ block: 'center', behavior: 'auto' });
  el.focus({ preventScroll: true });
  return { ok: document.activeElement === el, reason: document.activeElement === el ? '' : 'Controle não pôde receber foco.' };
}

async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs[0] || tabs[0].id == null) throw new Error('Não há guia ativa.');
  const url = tabs[0].url || '';
  if (!/^https?:\/\//i.test(url) && !/^file:\/\//i.test(url)) {
    throw new Error('Esta página interna do navegador não permite diagnóstico.');
  }
  return tabs[0];
}

async function scan(tab) {
  await requirePersistentAccess();
  let results;
  try {
    results = await chrome.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true }, func: inspectPageFrame
    });
  } catch (error) {
    throw new Error('Não foi possível examinar a página: ' + error.message);
  }
  const frames = results.map(({ frameId, result }) => ({ frameId, ...result }));
  const controls = frames.flatMap(frame => frame.controls.map(control => ({ frameId: frame.frameId, ...control })));
  return {
    site: (() => { try { return new URL(tab.url).hostname; } catch (_) { return 'site desconhecido'; } })(),
    framesInspected: frames.length,
    widgets: frames.flatMap(f => f.widgets).slice(0, 30),
    controls: controls.slice(0, 70),
    detected: frames.some(f => f.isLikelyChallenge)
  };
}

async function captureForAnalysis(tab) {
  await requirePersistentAccess();
  const diagnostics = await scan(tab);
  // A side panel remains open while the user changes tabs. Never capture a
  // different active tab than the one whose DOM was inspected.
  const current = await activeTab();
  if (current.id !== tab.id || current.url !== tab.url) {
    throw new Error('A guia mudou durante a análise. Repita o comando na guia desejada.');
  }
  const image = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'jpeg', quality: 68 });
  return { scan: diagnostics, image: image.split(',')[1] };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message?.type === 'HEALTH') {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 4000);
      try {
        const response = await fetch(`${SERVICE_URL}/health`, { signal: controller.signal });
        if (!response.ok) throw new Error('Falha do servidor.');
        return await response.json();
      } finally { clearTimeout(timer); }
    }
    const tab = await activeTab();
    if (message?.type === 'SCAN') return await scan(tab);
    if (message?.type === 'CAPTURE') return await captureForAnalysis(tab);
    if (message?.type === 'FOCUS') {
      await requirePersistentAccess();
      const { frameId, index, kind, label } = message.control || {};
      if (!Number.isInteger(frameId) || !Number.isInteger(index) || typeof label !== 'string' || label.length > 140) {
        throw new Error('Controle inválido.');
      }
      const result = await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [frameId] },
        func: focusControl, args: [index, kind, label]
      });
      return result[0]?.result || { ok: false, reason: 'Não localizado.' };
    }
    throw new Error('Ação desconhecida.');
  })().then(data => sendResponse({ ok: true, data }))
    .catch(error => sendResponse({ ok: false, error: error.message || String(error) }));
  return true;
});
