// Deliberately conservative: only the wide result-footer control, never ad copy.
() => {
  const labels = /^(see more|load more|show more|lihat lainnya|lihat lebih banyak|tampilkan lebih banyak|muat lebih banyak)$/i;
  const candidates = [...document.querySelectorAll('button, [role="button"], a')];
  for (const el of candidates.reverse()) {
    if (!labels.test((el.innerText || '').trim())) continue;
    if (el.closest('article, [role="article"], [role="dialog"], header, nav')) continue;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') continue;
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || r.height < 24 || r.height > 140) continue;
    // The result footer spans the feed; inline "See more" links do not.
    if (r.width < document.documentElement.clientWidth * .65) continue;
    if (r.top < innerHeight * .35 || r.bottom > innerHeight + 8) continue;
    if (el.tagName === 'A') {
      const href = el.getAttribute('href');
      if (href && href !== '#' && !href.startsWith('#')) continue;
    }
    // Exclude a full-width control inside a non-semantic ad card.
    let parent = el.parentElement;
    let inCard = false;
    for (let i = 0; parent && i < 5; i++, parent = parent.parentElement) {
      if (parent.getBoundingClientRect().width > r.width * 1.15) break;
      if (parent === document.body || parent === document.documentElement || parent.getBoundingClientRect().height > innerHeight * 1.5) break;
      const text = parent.innerText || '';
      if (/\b(?:Library ID|ID Pustaka|ID Perpustakaan|ID Galeri)\s*:?\s*\d{6,20}/i.test(text)) {
        inCard = true; break;
      }
    }
    if (inCard) continue;
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    if (!hit || !(hit === el || el.contains(hit))) continue;
    el.click();
    return true;
  }
  return false;
}
