// Shared data
const BOOK_META = [
  { abbr: "1-ne", chapters: 22 },
  { abbr: "2-ne", chapters: 33 },
  { abbr: "jacob", chapters: 7 },
  { abbr: "enos", chapters: 1 },
  { abbr: "jarom", chapters: 1 },
  { abbr: "omni", chapters: 1 },
  { abbr: "w-of-m", chapters: 1 },
  { abbr: "mosiah", chapters: 29 },
  { abbr: "alma", chapters: 63 },
  { abbr: "hel", chapters: 16 },
  { abbr: "3-ne", chapters: 30 },
  { abbr: "4-ne", chapters: 1 },
  { abbr: "morm", chapters: 9 },
  { abbr: "ether", chapters: 15 },
  { abbr: "moro", chapters: 10 },
];

// Utilities
function params() { return new URLSearchParams(window.location.search); }
function q(sel) { return document.querySelector(sel); }
function setBackLink() {
  const main = params().get("main");
  const second = params().get("second");
  const back = q("#back-link");
  if (back) back.href = `books.html?main=${encodeURIComponent(main || "por")}&second=${encodeURIComponent(second || "fra")}`;
}

// ------------------------------
// BOOKS PAGE
// ------------------------------
async function renderBooksPage() {
  const container = document.getElementById("book-list");
  if (!container) return;

  const main = params().get("main") || "por";
  const second = params().get("second") || "fra";

  // Fetch localized book names (silent fallback to slugs)
  let localized = {};
  try {
    const resp = await fetch(`/api/books?lang=${encodeURIComponent(main)}`, { cache: "no-store" });
    if (resp.ok) {
      const data = await resp.json();
      if (data && Array.isArray(data.books)) {
        for (const b of data.books) {
          if (b && b.abbr) localized[b.abbr] = (b.name || "").trim();
        }
      }
    }
  } catch (_) { /* silent fallback */ }

  // Chapter label from booksnames.json (silent fallback to "Chapter")
  let chapterWord = "Chapter";
  try {
    const res = await fetch("/booksnames.json", { cache: "no-store" });
    if (res.ok) {
      const all = await res.json();
      const ch = all?.[main]?.chapter?.toString().trim();
      const looksLikeWord =
        /[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF\u0590-\u06FF\u0900-\u097F]/.test(ch || "") ||
        /[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]/.test(ch || "");
      if (ch && looksLikeWord) chapterWord = ch;
    }
  } catch (_) { /* silent fallback */ }

  const isCJK = /[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]/.test(chapterWord);
  const makeChapterLabel = (n) => (isCJK ? `${n}${chapterWord}` : `${chapterWord} ${n}`);

  // ---------- helpers ----------
  const mkEl = (tag, cls, text) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text != null) el.textContent = text;
    return el;
  };

  const makeAccordionItem = (titleText) => {
    const item = mkEl("div", "acc-item");
    const btn = mkEl("button", "acc-button");
    const title = mkEl("span", "acc-title", titleText);
    const chev = mkEl("span", "acc-chevron");
    btn.appendChild(title);
    btn.appendChild(chev);
    const panel = mkEl("div", "acc-panel");
    btn.addEventListener("click", () => {
      item.classList.toggle("open");
    });
    item.appendChild(btn);
    item.appendChild(panel);
    return { item, panel, btn };
  };

  // ---------- render root accordion ----------
  container.innerHTML = "";
  const acc = mkEl("div", "accordion");
  container.appendChild(acc);

  // Top-level "Book of Mormon" dropdown
  const root = makeAccordionItem("Book of Mormon");
  acc.appendChild(root.item);

  // Inside it, render each book as its own dropdown (title → chapters)
  const booksWrap = mkEl("div", "books-wrap");
  root.panel.appendChild(booksWrap);

  for (const meta of BOOK_META) {
    const displayName =
      localized[meta.abbr] && !localized[meta.abbr].startsWith("<")
        ? localized[meta.abbr]
        : meta.abbr.toUpperCase();

    const book = makeAccordionItem(displayName);
    booksWrap.appendChild(book.item);

    // chapters list for this book
    const ul = mkEl("ul", "chapter-list");
    for (let i = 1; i <= meta.chapters; i++) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `chapter.html?book=${meta.abbr}&chapter=${i}&main=${encodeURIComponent(main)}&second=${encodeURIComponent(second)}`;
      a.textContent = makeChapterLabel(i);
      li.appendChild(a);
      ul.appendChild(li);
    }
    book.panel.appendChild(ul);
  }

  // Optional: start with everything collapsed (matches your sketch).
  // If you want the top "Book of Mormon" open by default, uncomment:
  // root.item.classList.add("open");
}

// ------------------------------
// Helpers for chapter meta rows
// ------------------------------
function escapeHtml(s = "") {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function prependMetaRow(container, label, leftText, rightText) {
  if (!container) return;

  const L = (leftText  ?? "").toString().trim();
  const R = (rightText ?? "").toString().trim();
  if (!L && !R) return;

  const row = document.createElement("div");
  row.className = "verse-row meta-row";

  const left = document.createElement("div");
  left.className = "verse-col";
  left.innerHTML = L
    ? `<div class="meta-text">${escapeHtml(L)}</div>`
    : `<div class="meta-text" style="opacity:.5">—</div>`;

  const right = document.createElement("div");
  right.className = "verse-col";
  right.innerHTML = R
    ? `<div class="meta-text">${escapeHtml(R)}</div>`
    : `<div class="meta-text" style="opacity:.5">—</div>`;

  row.appendChild(left);
  row.appendChild(right);
  container.insertBefore(row, container.firstChild);
}

// ------------------------------
// CHAPTER PAGE
// ------------------------------
async function loadChapter() {
  if (!window.location.pathname.endsWith("chapter.html")) return;

  setBackLink();

  const p = params();
  const book = p.get("book");
  const chapter = p.get("chapter");
  const main = p.get("main") || "spa";
  const second = p.get("second") || "eng";
  const bookKey = (book || "").trim().toLowerCase();
  const chNum = parseInt(chapter, 10) || 0;

  // Localized book names for header (silent fallback to slug)
  let localized = {};
  try {
    const resp = await fetch(`/api/books?lang=${encodeURIComponent(main)}`, { cache: "no-store" });
    if (resp.ok) {
      const data = await resp.json();
      if (data && Array.isArray(data.books)) {
        for (const b of data.books) {
          if (b && b.abbr) localized[b.abbr] = (b.name || "").trim();
        }
      }
    }
  } catch (_) { /* silent fallback */ }

  // Chapter label for header (localized; silent fallback)
  let chapterWord = "Chapter";
  try {
    const res = await fetch("/booksnames.json", { cache: "no-store" });
    if (res.ok) {
      const all = await res.json();
      const ch = all?.[main]?.chapter?.toString().trim();
      const looksLikeWord =
        /[A-Za-z\u00C0-\u024F\u0370-\u03FF\u0400-\u04FF\u0590-\u06FF\u0900-\u097F]/.test(ch || "") ||
        /[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]/.test(ch || "");
      if (ch && looksLikeWord) chapterWord = ch;
    }
  } catch (_) { /* silent fallback */ }

  const isCJK = /[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]/.test(chapterWord);
  const makeChapterLabel = (n) => (isCJK ? `${n}${chapterWord}` : `${chapterWord} ${n}`);

  const displayName =
    localized[book] && !localized[book].startsWith("<")
      ? localized[book]
      : (book || "").toUpperCase();

  const headerEl = document.getElementById("chapter-title");
  if (headerEl) {
  headerEl.innerHTML = `
    <span class="book-name">${displayName}</span>
    <span class="chapter-sep"> – </span>
    <span class="chapter-name">${makeChapterLabel(chapter)}</span>
  `;
}

  // Prev/Next buttons
  const bookMeta = BOOK_META.find(b => b.abbr === book);
  const prevBtn = document.getElementById("prev-chapter");
  const nextBtn = document.getElementById("next-chapter");

  const currentChapter = parseInt(chapter, 10);
  const totalChapters = bookMeta ? bookMeta.chapters : 0;
  const bookIndex = BOOK_META.findIndex(b => b.abbr === book);

  let nextBookAbbr = book;
  let nextChapterNum = currentChapter + 1;
  if (currentChapter >= totalChapters) {
    const nb = (bookIndex + 1) % BOOK_META.length;
    nextBookAbbr = BOOK_META[nb].abbr;
    nextChapterNum = 1;
  }

  let prevBookAbbr = book;
  let prevChapterNum = currentChapter - 1;
  if (currentChapter <= 1) {
    const pb = (bookIndex - 1 + BOOK_META.length) % BOOK_META.length;
    prevBookAbbr = BOOK_META[pb].abbr;
    prevChapterNum = BOOK_META[pb].chapters;
  }

  if (prevBtn) {
    prevBtn.href = `chapter.html?book=${prevBookAbbr}&chapter=${prevChapterNum}&main=${main}&second=${second}`;
    prevBtn.removeAttribute("aria-disabled");
  }
  if (nextBtn) {
    nextBtn.href = `chapter.html?book=${nextBookAbbr}&chapter=${nextChapterNum}&main=${main}&second=${second}`;
    nextBtn.removeAttribute("aria-disabled");
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft" && prevBtn && prevBtn.href) window.location.href = prevBtn.href;
    if (e.key === "ArrowRight" && nextBtn && nextBtn.href) window.location.href = nextBtn.href;
  });

  // Badges/labels
  const badges = document.getElementById("lang-badges");
  if (badges) {
    badges.innerHTML = `
      <span class="badge">Main: ${main.toUpperCase()}</span>
      <span class="badge">Second: ${second.toUpperCase()}</span>`;
  }
  const colLeft = document.getElementById("col-left");
  const colRight = document.getElementById("col-right");
  if (colLeft) colLeft.textContent = `${main.toUpperCase()}`;
  if (colRight) colRight.textContent = `${second.toUpperCase()}`;

  // Verses container
  const container = document.getElementById("verse-container");
  if (!container) { console.warn("No #verse-container found"); return; }

  const getVersesViaProxy = async (lang) => {
    const url = `/api/chapter?book=${encodeURIComponent(book)}&chapter=${encodeURIComponent(chapter)}&lang=${encodeURIComponent(lang)}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Proxy error: ${resp.status}`);
    const data = await resp.json();
    return data.verses || [];
  };

  let mainVerses = [];
  let secondVerses = [];
  try {
    [mainVerses, secondVerses] = await Promise.all([getVersesViaProxy(main), getVersesViaProxy(second)]);
  } catch (e) {
    console.error("Proxy fetch error:", e);
    if (container) {
      const div = document.createElement("div");
      div.className = "verse-row error";
      div.textContent = "Unable to fetch content via proxy. Make sure the Flask server is running (see README).";
      container.appendChild(div);
    }
    return;
  }

  // 1 Nephi 1: prepend subtitle + introduction rows
  if (bookKey === "1-ne" && chNum === 1) {
    try {
      const [mainExtras, secondExtras] = await Promise.all([
        fetch(`/api/intro?book=${encodeURIComponent(bookKey)}&chapter=${chNum}&lang=${encodeURIComponent(main)}`,   { cache: "no-store" })
          .then(r => (r.ok ? r.json() : { subtitle: "", introduction: "" })),
        fetch(`/api/intro?book=${encodeURIComponent(bookKey)}&chapter=${chNum}&lang=${encodeURIComponent(second)}`, { cache: "no-store" })
          .then(r => (r.ok ? r.json() : { subtitle: "", introduction: "" })),
      ]);

      prependMetaRow(
        container,
        "Introduction",
        (mainExtras.introduction ?? "").toString(),
        (secondExtras.introduction ?? "").toString()
      );
      prependMetaRow(
        container,
        "Book subtitle",
        (mainExtras.subtitle ?? "").toString(),
        (secondExtras.subtitle ?? "").toString()
      );
    } catch (_) { /* silent: meta rows are optional */ }
  }

  // Render verses
  const maxLen = Math.max(mainVerses.length, secondVerses.length);
  for (let i = 0; i < maxLen; i++) {
    const row = document.createElement("div");
    row.className = "verse-row";

    // Helper to format: "1 And it came to pass..."
    const formatVerse = (vObj) => {
      if (!vObj) return "";
      // Handle new object format { verse: "1", text: "..." }
      if (typeof vObj === 'object' && vObj.text) {
        return `<span class="v-num"><b>${vObj.verse}</b></span> ${vObj.text}`;
      }
      // Fallback for string-only data (if any)
      return vObj;
    };

    const col1 = document.createElement("div");
    col1.className = "verse-col";
    col1.innerHTML = formatVerse(mainVerses[i]);

    const col2 = document.createElement("div");
    col2.className = "verse-col";
    col2.innerHTML = formatVerse(secondVerses[i]);
    row.appendChild(col1);
    row.appendChild(col2);

    container.appendChild(row);
  }
  // Force default Single view AFTER verses render
  if (window.__enterSingleView) window.__enterSingleView();
}

// Router-ish init
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("book-list")) renderBooksPage();
  loadChapter();
  setupAccountMenu();
});

/* --- Single vs Parallel view toggle --- */
(function () {
  function setupToggle() {
    const container   = document.getElementById('verse-container');
    const btnParallel = document.getElementById('view-parallel');
    const btnSingle   = document.getElementById('view-single');
    if (!container || !btnParallel || !btnSingle) return false;

    let parallelHTML = null; // cache original rows

    function setActive(btn) {
      [btnParallel, btnSingle].forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
    }

    function enterSingleView() {
      if (!parallelHTML) parallelHTML = container.innerHTML;

      const rows = Array.from(container.querySelectorAll('.verse-row'));
      if (rows.length) {
        const items = rows.map((row, idx) => {
          const left  = row.querySelector('.verse-col:nth-child(1)');
          const right = row.querySelector('.verse-col:nth-child(2)');
          const wrap = document.createElement('div');
          wrap.className = 'verse-item';
          wrap.setAttribute('role', 'button');
          wrap.setAttribute('tabindex', '0');
          wrap.setAttribute('aria-expanded', 'false');
          wrap.dataset.verseIndex = String(idx + 1);
          const vMain = document.createElement('div');
          vMain.className = 'v-main';
          vMain.innerHTML = left ? left.innerHTML : '';
          const vSecond = document.createElement('div');
          vSecond.className = 'v-second';
          vSecond.innerHTML = right ? right.innerHTML : '';
          wrap.appendChild(vMain);
          wrap.appendChild(vSecond);
          return wrap;
        });
        container.innerHTML = '';
        items.forEach(n => container.appendChild(n));
      }
      document.body.classList.add('single-view');
      setActive(btnSingle);
    }

    function enterParallelView() {
      if (parallelHTML != null) container.innerHTML = parallelHTML;
      document.body.classList.remove('single-view');
      setActive(btnParallel);
    }

    // Click + keyboard toggle for verse items
    container.addEventListener('click', (e) => {
      const item = e.target.closest('.verse-item');
      if (!item) return;
      item.classList.toggle('open');
      item.setAttribute('aria-expanded', item.classList.contains('open') ? 'true' : 'false');
    });
    container.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        const item = e.target.closest('.verse-item');
        if (!item) return;
        e.preventDefault();
        item.classList.toggle('open');
        item.setAttribute('aria-expanded', item.classList.contains('open') ? 'true' : 'false');
      }
    });

    // Wire up buttons
    btnSingle.addEventListener('click', enterSingleView);
    btnParallel.addEventListener('click', enterParallelView);

    // Expose so loadChapter can force default after fetch/render
    window.__enterSingleView   = enterSingleView;
    window.__enterParallelView = enterParallelView;
    return true;
  }

  if (!setupToggle()) {
    document.addEventListener('DOMContentLoaded', setupToggle, { once: true });
  }
})();

/* ================= ACCOUNT MENU ======================================== */
function setupAccountMenu(){
  const btn  = document.getElementById('account-btn');
  const menu = document.getElementById('account-menu');
  if (!btn || !menu) return;

  function closeMenu(){
    if (!menu.hidden){
      menu.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
    }
  }
  function toggleMenu(e){
    e?.stopPropagation();
    const willOpen = menu.hidden;
    // close any other open menu (if any page duplicates)
    document.querySelectorAll('.account-menu').forEach(m => { if (m !== menu) m.hidden = true; });
    menu.hidden = !willOpen ? true : false;
    btn.setAttribute('aria-expanded', String(willOpen));
  }
  btn.addEventListener('click', toggleMenu);
  document.addEventListener('click', (e) => {
    if (!menu.hidden && !menu.contains(e.target) && e.target !== btn) closeMenu();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });

  // Populate menu based on auth state
  fetch("/api/me", { credentials: "same-origin", cache: "no-store" })
    .then(r => r.ok ? r.json() : { authenticated:false })
    .then(me => {
      if (me.authenticated) {
        menu.innerHTML = `
          <a role="menuitem" href="/login">Login</a>
          <a role="menuitem" href="/signup">Sign up</a>
          <a role="menuitem" href="/password/forgot">Forgot password</a>
        `;
      } else {
        menu.innerHTML = `
          <a role="menuitem" href="/login">Login</a>
          <a role="menuitem" href="/signup">Sign up</a>
        `;
      }
    })
    .catch(() => {/* keep defaults */});
}


/* ================= THEME: persistence + toggle ========================== */
(function () {
  const THEME_KEY = "bom_theme"; // "light" | "dark"

  function getMetaTheme() {
    let m = document.querySelector('meta[name="theme-color"]');
    if (!m) {
      m = document.createElement('meta');
      m.name = 'theme-color';
      document.head.appendChild(m);
    }
    return m;
  }

  function applyTheme(theme) {
    const root = document.documentElement;
    const isDark = theme === 'dark';
    root.classList.toggle('theme-dark', isDark);
    try { localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light'); } catch {}

    // Sync browser UI color with CSS var(--banner)
    const bannerColor = getComputedStyle(root).getPropertyValue('--banner').trim() || (isDark ? '#312706' : '#879375');
    const meta = getMetaTheme();
    meta.setAttribute('content', bannerColor);
  }

  function currentTheme() {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === 'dark' || saved === 'light') return saved;
    } catch {}
    return 'light';
  }

  function buildToggle() {
    const wrap = document.createElement('div');
    wrap.className = 'theme-toggle';

    const btnLight = document.createElement('button');
    btnLight.type = 'button';
    btnLight.textContent = 'Light';
    btnLight.setAttribute('aria-pressed', currentTheme() === 'light' ? 'true' : 'false');

    const btnDark = document.createElement('button');
    btnDark.type = 'button';
    btnDark.textContent = 'Dark';
    btnDark.setAttribute('aria-pressed', currentTheme() === 'dark' ? 'true' : 'false');

    function setPressed(light) {
      btnLight.setAttribute('aria-pressed', light ? 'true' : 'false');
      btnDark.setAttribute('aria-pressed', light ? 'false' : 'true');
    }

    btnLight.addEventListener('click', () => { applyTheme('light'); setPressed(true); });
    btnDark.addEventListener('click', () => { applyTheme('dark');  setPressed(false); });

    wrap.appendChild(btnLight);
    wrap.appendChild(btnDark);
    return wrap;
  }

  function ensureControlsBar() {
    let controls = document.querySelector('.controls');
    if (!controls) {
      const page = document.querySelector('.page') || document.body;
      const header = page.querySelector('header.topbar') || page.querySelector('header') || page.firstElementChild;
      controls = document.createElement('div');
      controls.className = 'controls';
      if (header && header.parentNode) {
        header.parentNode.insertBefore(controls, header.nextSibling);
      } else {
        page.insertBefore(controls, page.firstChild);
      }
    }
    return controls;
  }

  function insertThemeToggle() {
    const controls = ensureControlsBar();
    if (!controls.querySelector('.theme-toggle')) {
      controls.appendChild(buildToggle());
    }
  }

  // Run early
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(currentTheme());
    insertThemeToggle();
  }, { once: true });
})();

