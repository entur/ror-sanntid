// In-page anchor scrolling (works inside preview frames where hash nav is intercepted)
document.querySelectorAll('a[href^="#"]').forEach(function (a) {
  a.addEventListener("click", function (e) {
    var id = a.getAttribute("href").slice(1);
    if (!id) return;
    var t = document.getElementById(id);
    if (!t) return;
    e.preventDefault();
    var y =
      t.getBoundingClientRect().top +
      (window.scrollY || document.documentElement.scrollTop);
    window.scrollTo({ top: y, behavior: "smooth" });
  });
});

// Accordions (SIRI ET / VM / SX)
document.querySelectorAll(".acc-head").forEach(function (head) {
  head.addEventListener("click", function () {
    var acc = head.closest(".acc");
    var body = acc.querySelector(".acc-body");
    var open = acc.classList.toggle("open");
    head.setAttribute("aria-expanded", String(open));
    body.style.maxHeight = open ? body.scrollHeight + "px" : "0px";
  });
});

// Collapsible detail block (Standardformater …) controlled by the two chevrons
(function () {
  var block = document.getElementById("detail-block");
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
  setChevrons(!block.hasAttribute("hidden"));
  btns.forEach(function (b) {
    if (b) b.addEventListener("click", toggle);
  });
})();
