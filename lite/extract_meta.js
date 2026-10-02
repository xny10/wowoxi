// AdRadar Lite Turbo extractor.
// Stateful/incremental: the first call scans the current DOM once, subsequent calls
// only inspect nodes added/changed since the previous drain.
() => {
  const LABELS = [
    'Library ID', 'ID Perpustakaan', 'ID Pustaka', 'ID Galeri', 'ID Iklan', 'ID Iklan Galeri',
    'Gallery ID', 'Ad ID', 'ID della libreria', 'Bibliotheks-ID', 'ID de la biblioteca',
    'ID de la bibliothèque', 'ID biblioteki', 'Kütüphane Kimliği', 'ライブラリID',
    '라이브러리 ID', '库 ID', '庫 ID', 'معرف المكتبة', 'รหัสคลัง',
  ];

  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const labelAlt = LABELS.map(esc).join('|');
  const strictSource = `(?:${labelAlt}):?\\s*(\\d{6,20})`;
  const genericSource = String.raw`\b(?:(?:[A-Za-zÀ-ɏ]+\s+){0,2}ID|ID(?:\s+[A-Za-zÀ-ɏ]+){0,3})\s*:?\s*(\d{10,20})\b`;
  const libIdRegex = new RegExp(`${strictSource}|${genericSource}`, 'i');
  const libIdRegexG = new RegExp(`(?:${labelAlt}):?\\s*\\d{6,20}|${genericSource.replace('(\\d{10,20})', '\\d{10,20}')}`, 'gi');
  const libIdSubstringRegex = new RegExp(`(?:${labelAlt}):?|${genericSource.replace('(\\d{10,20})', '\\d{10,20}')}`, 'i');

  const destination = raw => {
    try {
      let u = new URL(raw);
      const host = u.hostname.toLowerCase();
      if ((host === 'facebook.com' || host.endsWith('.facebook.com')) && /\/(l\.php|flx\/warn)/.test(u.pathname)) {
        const value = ['u', 'url', 'target', 'redirect_uri', 'next'].map(k => u.searchParams.get(k)).find(Boolean);
        if (!value) return '';
        u = new URL(value);
      }
      if (!['http:', 'https:'].includes(u.protocol)) return '';
      if (['facebook.com', 'fb.com', 'fbcdn.net', 'instagram.com', 'messenger.com'].some(h => u.hostname === h || u.hostname.endsWith('.' + h))) return '';
      return u.href;
    } catch { return ''; }
  };

  const makeState = () => {
    const state = {
      pending: [],
      queued: new WeakSet(),
      seenPairs: new Set(),
      seenAdIds: new Set(),
      generation: 0,
      observer: null,
      watched: new WeakSet(),
      visibilityObserver: null,
      initializedAt: Date.now(),
    };

    state.queue = node => {
      if (!node) return;
      let el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
      if (!(el instanceof Element) || !el.isConnected || state.queued.has(el)) return;
      state.queued.add(el);
      state.pending.push(el);
      // Protect against pathological mutation storms. Dropping old queue entries is safe:
      // later mutations/scrolls will enqueue nearby content again, while the initial body scan
      // already covers everything present at startup.
      if (state.pending.length > 4000) {
        const dropped = state.pending.splice(0, state.pending.length - 3000);
        for (const old of dropped) state.queued.delete(old);
      }
    };

    state.visibilityObserver = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) state.queue(entry.target);
    }, {rootMargin: '800px 0px'});
    state.queue(document.body);
    state.observer = new MutationObserver(mutations => {
      for (const m of mutations) {
        if (m.type === 'childList') {
          for (const node of m.addedNodes) state.queue(node);
        } else if (m.type === 'characterData') {
          state.queue(m.target.parentElement);
        } else if (m.type === 'attributes') {
          // href changes often occur below the Library ID text. Queue a bounded ancestor
          // instead of the whole document so a late-loaded destination URL can be captured.
          let el = m.target;
          for (let i = 0; i < 8 && el?.parentElement; i++) el = el.parentElement;
          state.queue(el || m.target);
        }
      }
    });
    state.observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['href'],
    });
    return state;
  };

  const state = window.__adradarLiteTurbo || (window.__adradarLiteTurbo = makeState());
  const roots = [];
  // Bound work per Python polling cycle. Usually the queue is much smaller than this.
  for (let i = 0; i < 240 && state.pending.length; i++) {
    const root = state.pending.shift();
    state.queued.delete(root);
    if (root?.isConnected) roots.push(root);
  }

  // Rare fallback probe. MutationObserver is the main path; probing only once every
  // 10 empty drains prevents a hidden large feed ancestor from being rescanned repeatedly.
  state.emptyDrains = roots.length ? 0 : (state.emptyDrains || 0) + 1;
  if (!roots.length && state.emptyDrains % 10 === 0) {
    const probe = document.elementFromPoint(Math.max(1, innerWidth / 2), Math.max(1, innerHeight - 40));
    if (probe) {
      const article = probe.closest('article, [role="article"]');
      const bounded = article || probe.parentElement?.parentElement?.parentElement || probe;
      if (bounded?.isConnected) roots.push(bounded);
    }
  }

  const idCounts = new WeakMap();
  const countIds = el => {
    if (!idCounts.has(el)) {
      const ids = new Set();
      for (const m of (el.textContent || '').matchAll(libIdRegexG)) {
        const n = m[0].match(/\d{6,20}/)?.[0];
        if (n) ids.add(n);
        if (ids.size > 1) break;
      }
      idCounts.set(el, ids.size);
    }
    return idCounts.get(el);
  };

  const candidates = [];
  const candidateKeys = new Set();
  const addTextNode = textNode => {
    const parent = textNode?.parentElement;
    if (!parent?.isConnected) return;
    if (!state.watched.has(parent)) {
      state.watched.add(parent);
      state.visibilityObserver.observe(parent);
    }
    const rect = parent.getBoundingClientRect();
    // Only parse cards around the current viewport. Newly appended feed cards are normally
    // in this band; this avoids doing work on thousands of old cards above the viewport.
    if (rect.bottom < -innerHeight || rect.top > innerHeight * 2.5) return;
    const match = (textNode.textContent || '').match(libIdRegex);
    const adId = match && (match[1] || match[2]);
    if (!adId) return;

    let container = parent;
    let best = null;
    for (let i = 0; i < 20; i++) {
      if (!container?.parentElement) break;
      container = container.parentElement;
      const r = container.getBoundingClientRect();
      if (r.width < 120 || r.height < 40) continue;
      const idCount = countIds(container);
      if (idCount === 1) best = container;
      else if (idCount > 1) break;
    }
    const article = parent.closest('article, [role="article"]');
    if (article && countIds(article) === 1) best = article;
    if (!best) return;

    // Safe rendering optimization: let the browser skip layout/paint work for cards far
    // outside the viewport without removing React-managed DOM nodes.
    try {
      best.style.contentVisibility = 'auto';
      best.style.containIntrinsicSize = 'auto 520px';
    } catch {}

    if (!candidateKeys.has(adId)) {
      candidateKeys.add(adId);
      candidates.push({container: best, adId});
    }
    if (!state.seenAdIds.has(adId)) {
      state.seenAdIds.add(adId);
      state.generation++;
    }
  };

  for (const root of roots) {
    if (!root?.isConnected) continue;
    // Handle a text-only root/leaf quickly before walking descendants.
    if (root.children?.length === 0 && libIdSubstringRegex.test(root.textContent || '')) {
      for (const node of root.childNodes) if (node.nodeType === Node.TEXT_NODE) addTextNode(node);
    }
    const walker = document.createTreeWalker(
      root,
      NodeFilter.SHOW_TEXT,
      {acceptNode: node => libIdSubstringRegex.test(node.textContent || '') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT}
    );
    while (walker.nextNode()) addTextNode(walker.currentNode);
  }

  const rows = [];
  for (const {container, adId} of candidates) {
    const text = container.innerText || '';
    const lines = text.split('\n').map(t => t.trim().toLowerCase());
    let status = 'unknown';
    if (lines.some(t => /^(inactive|tidak aktif|nonaktif)$/.test(t))) status = 'inactive';
    else if (lines.some(t => /^(active|aktif)$/.test(t))) status = 'active';

    const urls = new Set();
    for (const a of container.querySelectorAll('a[href]')) {
      const d = destination(a.href);
      if (d) urls.add(d);
    }
    if (!urls.size) {
      for (const raw of text.match(/https?:\/\/[^\s"'<>]+/gi) || []) {
        const d = destination(raw.replace(/[),.;]+$/, ''));
        if (d) urls.add(d);
      }
    }
    for (const url of urls) {
      const key = `${adId}\u0000${url}`;
      if (state.seenPairs.has(key)) continue;
      state.seenPairs.add(key);
      rows.push({adId, destinationUrl: url, adStatus: status});
    }
  }

  return {
    rows,
    containers: candidates.length,
    newRows: rows.length,
    totalCards: state.seenAdIds.size,
    generation: state.generation,
    pending: state.pending.length,
    scrollY: window.scrollY,
    height: Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0),
  };
}
