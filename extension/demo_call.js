// Offline demo-call tab (T22): plays local clips the presenter picks, one after another.
// Files stay on this laptop (object URLs); nothing is uploaded, stored or bundled.
(function () {
  const input = document.getElementById("files");
  const list = document.getElementById("playlist");
  const player = document.getElementById("player");
  const next = document.getElementById("next");
  let files = [];
  let current = -1;
  let url = null;

  function play(i) {
    if (i < 0 || i >= files.length) return;
    if (url) URL.revokeObjectURL(url);
    url = URL.createObjectURL(files[i]);
    current = i;
    player.src = url;
    player.play().catch(() => {}); // autoplay may need one click; the controls are there
    Array.from(list.children).forEach((li, j) => li.classList.toggle("playing", j === i));
  }

  input.addEventListener("change", () => {
    files = Array.from(input.files || []);
    list.innerHTML = "";
    files.forEach((f, i) => {
      const li = document.createElement("li");
      li.textContent = f.name;
      li.addEventListener("click", () => play(i));
      list.appendChild(li);
    });
    if (files.length) play(0);
  });
  next.addEventListener("click", () => play(current + 1));
  player.addEventListener("ended", () => play(current + 1));
})();
