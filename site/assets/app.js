// In-page anchor scrolling is left to the browser: CSS `scroll-behavior: smooth`
// (styles.css, disabled under prefers-reduced-motion) does the animation, while
// the browser keeps the URL hash, the history entry, focus and modifier-clicks
// working. The bundled original preventDefault'd all of that to work around
// hash navigation being intercepted inside the artifact preview frame, which
// does not apply here.

// Collapse on init. The markup ships expanded so the content is readable,
// findable and linkable without JavaScript; the collapsed state is a
// progressive enhancement applied only once we know JS is running.
document.querySelectorAll(".acc.open").forEach(function (acc) {
  var head = acc.querySelector(".acc-head");
  var body = acc.querySelector(".acc-body");
  if (!head || !body) return;
  acc.classList.remove("open");
  head.setAttribute("aria-expanded", "false");
  body.style.maxHeight = "0px";
});

// Accordions (SIRI ET / VM / SX)
document.querySelectorAll(".acc-head").forEach(function (head) {
  head.addEventListener("click", function () {
    var acc = head.closest(".acc");
    if (!acc) return;
    var body = acc.querySelector(".acc-body");
    if (!body) return;
    var open = acc.classList.toggle("open");
    head.setAttribute("aria-expanded", String(open));
    if (open) {
      // Animate to the measured height, then unpin: a fixed pixel max-height
      // clips the panel after any later reflow (resize, font swap).
      body.style.maxHeight = body.scrollHeight + "px";
      body.addEventListener("transitionend", function done(e) {
        if (e.propertyName !== "max-height") return;
        body.removeEventListener("transitionend", done);
        if (acc.classList.contains("open")) body.style.maxHeight = "none";
      });
    } else {
      // Re-pin the current height so the collapse has something to animate from.
      body.style.maxHeight = body.scrollHeight + "px";
      void body.offsetHeight;
      body.style.maxHeight = "0px";
    }
  });
});

// Collapsible detail block (Standardformater …) controlled by the two chevrons
(function () {
  var block = document.getElementById("detail-block");
  if (!block) return;
  // Ships visible for no-JS readers; collapse it now that JS is running.
  block.setAttribute("hidden", "");
  var btns = [
    document.getElementById("chevTop"),
    document.getElementById("chevBottom"),
  ];
  var DOWN = "6 9 12 15 18 9",
    UP = "18 15 12 9 6 15";
  function setChevrons(open) {
    // open: top points up, bottom points down. collapsed: top down, bottom up.
    var p0 = btns[0] && btns[0].querySelector("polyline");
    var p1 = btns[1] && btns[1].querySelector("polyline");
    if (p0) p0.setAttribute("points", open ? UP : DOWN);
    if (p1) p1.setAttribute("points", open ? DOWN : UP);
  }
  function toggle() {
    var isHidden = block.hasAttribute("hidden");
    if (isHidden) {
      block.removeAttribute("hidden");
    } else {
      block.setAttribute("hidden", "");
    }
    btns.forEach(function (b) {
      if (b) b.setAttribute("aria-expanded", String(isHidden));
    });
    setChevrons(isHidden);
  }
  // Markup ships expanded for no-JS readers, so sync the controls to the
  // collapsed state applied above rather than trusting the static attribute.
  btns.forEach(function (b) {
    if (b) b.setAttribute("aria-expanded", "false");
  });
  setChevrons(!block.hasAttribute("hidden"));
  btns.forEach(function (b) {
    if (b) b.addEventListener("click", toggle);
  });
})();
