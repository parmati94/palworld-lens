/**
 * One tooltip for the whole app.
 *
 *   <button data-tip="Reset view">…</button>
 *   <span :data-tip="'Owned by ' + owner">…</span>
 *
 * A single fixed box is appended to <body> and driven by event delegation, so
 * it works for anything Alpine renders later and is never clipped by an
 * overflow/transform ancestor (the reason the old CSS ::after tooltips were
 * abandoned for native `title` in most places). The text is read from the
 * attribute at show time, so dynamic `:data-tip` bindings just work.
 *
 * Placement: centred above the element, flipped below when there's no room,
 * clamped to the viewport. Hover only on devices that have hover; keyboard
 * focus shows it everywhere. Hidden on pointerdown, scroll and Escape.
 */

const SHOW_DELAY = 90;   // ms before a hover tooltip appears
const GAP = 8;           // px between element and box
const EDGE = 8;          // px viewport margin

export function installTooltips() {
    if (typeof document === 'undefined' || document.getElementById('pw-tip')) return;

    const box = document.createElement('div');
    box.id = 'pw-tip';
    box.className = 'pw-tip';
    box.setAttribute('role', 'tooltip');
    box.hidden = true;
    document.body.appendChild(box);

    const canHover = window.matchMedia && window.matchMedia('(hover: hover)').matches;
    let current = null;      // element the tooltip is for
    let timer = null;
    let suppressed = null;   // element tapped/clicked: don't show until the pointer leaves it

    const target = (node) => (node instanceof Element ? node.closest('[data-tip]') : null);

    function place(el) {
        const text = el.getAttribute('data-tip');
        if (!text) { hide(); return; }
        box.textContent = text;
        box.hidden = false;
        box.dataset.placement = 'top';
        const r = el.getBoundingClientRect();
        const b = box.getBoundingClientRect();
        let top = r.top - b.height - GAP;
        if (top < EDGE) { top = r.bottom + GAP; box.dataset.placement = 'bottom'; }
        let left = r.left + r.width / 2 - b.width / 2;
        left = Math.max(EDGE, Math.min(left, window.innerWidth - b.width - EDGE));
        box.style.top = `${Math.round(top)}px`;
        box.style.left = `${Math.round(left)}px`;
        // Arrow follows the element even when the box is clamped to an edge.
        box.style.setProperty('--tip-arrow', `${Math.round(r.left + r.width / 2 - left)}px`);
        box.classList.add('is-visible');
    }

    function show(el, immediate) {
        if (!el || el === suppressed) return;
        clearTimeout(timer);
        current = el;
        if (immediate) place(el);
        else timer = setTimeout(() => { if (current === el && el.isConnected) place(el); }, SHOW_DELAY);
    }

    function hide() {
        clearTimeout(timer);
        current = null;
        box.classList.remove('is-visible');
        box.hidden = true;
    }

    if (canHover) {
        document.addEventListener('mouseover', (e) => {
            const el = target(e.target);
            if (!el) { if (current) hide(); return; }
            if (el !== current) show(el, false);
        });
        document.addEventListener('mouseout', (e) => {
            const el = target(e.target);
            if (!el || el !== current) return;
            if (e.relatedTarget instanceof Node && el.contains(e.relatedTarget)) return;
            hide();
            if (suppressed === el) suppressed = null;
        });
    }
    document.addEventListener('focusin', (e) => { const el = target(e.target); if (el) show(el, true); });
    document.addEventListener('focusout', (e) => { if (target(e.target) === current) hide(); });
    document.addEventListener('pointerdown', (e) => { suppressed = target(e.target); hide(); }, true);
    document.addEventListener('scroll', hide, true);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
    window.addEventListener('resize', hide);
    // The element under the pointer may be re-rendered by Alpine; drop the tip
    // if it is gone rather than leave it floating.
    new MutationObserver(() => { if (current && !current.isConnected) hide(); })
        .observe(document.body, { childList: true, subtree: true });
}
