/* アプリ画面のデモ用の動き。点数が変わったら前の値から数え上げ、数字を軽く弾ませる。
   デモ本体のコードには手を入れず、表示の書き換えを見張って後から動きを足す。 */
(function () {
  "use strict";
  if (!window.MutationObserver) return;
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  function parse(s) {
    var m = /^([+\-]?)(\d+)(pt)?$/.exec(String(s).replace("±", "").trim());
    if (!m) return null;
    return { n: (m[1] === "-" ? -1 : 1) * +m[2], pt: !!m[3] };
  }
  function fmt(n, pt) {
    if (pt) return (n > 0 ? "+" + n : String(n)) + "pt";
    return n > 0 ? "+" + n : n < 0 ? String(n) : "±0";
  }
  function bump(el, cls) {
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
  }
  function countUp(el, from, to) {
    cancelAnimationFrame(el._sqRaf);
    var t0 = performance.now(), dur = Math.min(650, 280 + Math.abs(to.n - from.n) * 4);
    (function step(now) {
      var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el._sqWritten = k < 1 ? fmt(Math.round(from.n + (to.n - from.n) * e), to.pt) : el._sqTarget;
      el.textContent = el._sqWritten;
      if (k < 1) el._sqRaf = requestAnimationFrame(step);
    })(t0);
    // 画面が裏にあってコマ送りが止まっても、最後は必ず正しい値にする
    clearTimeout(el._sqEnd);
    el._sqEnd = setTimeout(function () {
      cancelAnimationFrame(el._sqRaf);
      el._sqWritten = el._sqTarget;
      el.textContent = el._sqTarget;
    }, dur + 80);
  }

  var nodes = document.querySelectorAll(".rpt, .prow2 > span[id^='pg'], .stk");
  var mo = new MutationObserver(function (recs) {
    var seen = [];
    recs.forEach(function (r) {
      var el = r.target.nodeType === 1 ? r.target : r.target.parentNode;
      if (seen.indexOf(el) < 0) seen.push(el);
    });
    seen.forEach(function (el) {
      var t = el.textContent;
      if (t === el._sqWritten) return;          // 数え上げ中の自分の書き換え
      cancelAnimationFrame(el._sqRaf);
      clearTimeout(el._sqEnd);
      var prev = el._sqTarget;
      el._sqTarget = t;
      if (t === prev) return;
      var a = parse(prev), b = parse(t);
      if (!el.classList.contains("stk") && a && b && Math.abs(b.n - a.n) > 1) countUp(el, a, b);
      bump(el, "bump");
      if (el.id && el.id.indexOf("pg") === 0 && el.parentNode) bump(el.parentNode, "flash");
    });
  });
  Array.prototype.forEach.call(nodes, function (el) {
    el._sqTarget = el.textContent;
    mo.observe(el, { childList: true, characterData: true, subtree: true });
  });
})();
