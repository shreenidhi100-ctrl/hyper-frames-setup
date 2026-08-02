// Interprets a scene spec (see server.py SCENE_SCHEMA) and animates it live
// on a canvas, styled as a hand-drawn flipbook: notebook paper, a spiral
// binding, and — the actual flipbook signature — motion stepped to discrete
// "pages" per second rather than smooth 60fps tweening, with the linework
// redrawn with a small deterministic jitter each page (the hand-drawn
// "boil"). No pre-rendering, no export — just a live requestAnimationFrame
// loop that re-derives everything from elapsed time.

(function () {
  let currentFrame = null;
  let paperLayer = null; // offscreen cache of the (static) paper texture

  const PAGE_FPS = 10; // pages flipped per second
  const INK = "#2e2a24";
  const PAPER = "#f3ecd8";

  // ---- deterministic per-page jitter (the "boil") ------------------------
  function hashSeed(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function mulberry32(seed) {
    let a = seed;
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let x = Math.imul(a ^ (a >>> 15), 1 | a);
      x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
      return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
    };
  }

  function jitterFor(id, pageIndex) {
    const rnd = mulberry32(hashSeed(id) ^ (pageIndex * 2654435761));
    return {
      dx: (rnd() - 0.5) * 3,
      dy: (rnd() - 0.5) * 3,
      rot: (rnd() - 0.5) * 0.035,
    };
  }

  // ---- easing --------------------------------------------------------------
  function easeOutCubic(p) {
    return 1 - Math.pow(1 - p, 3);
  }

  // simple back-out overshoot for "pop" entrances
  function easeOutBack(p) {
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
  }

  function lerp(a, b, p) {
    return a + (b - a) * p;
  }

  function entranceProgress(el, t) {
    const { at, duration } = el.enter;
    if (t < at) return 0;
    const raw = duration > 0 ? Math.min(1, (t - at) / duration) : 1;
    return el.enter.style === "pop" ? easeOutBack(raw) : easeOutCubic(raw);
  }

  function pulseScale(el, t) {
    if (!el.loop || el.loop.type !== "pulse") return 1;
    const from = el.loop.from ?? el.enter.at + el.enter.duration;
    if (t < from) return 1;
    return 1 + 0.06 * Math.sin(((t - from) / 1.4) * Math.PI * 2);
  }

  // ---- paper texture (built once per canvas size, then just blitted) -------
  function buildPaperLayer(w, h) {
    const off = document.createElement("canvas");
    off.width = w;
    off.height = h;
    const c = off.getContext("2d");

    c.fillStyle = PAPER;
    c.fillRect(0, 0, w, h);

    // faint grain
    const rnd = mulberry32(42);
    const dots = Math.floor((w * h) / 900);
    for (let i = 0; i < dots; i++) {
      c.fillStyle = `rgba(60,50,30,${(rnd() * 0.05).toFixed(3)})`;
      c.fillRect(rnd() * w, rnd() * h, 1, 1);
    }

    // ruled lines
    c.strokeStyle = "rgba(90,110,140,0.35)";
    c.lineWidth = 1;
    for (let y = 60; y < h; y += 34) {
      c.beginPath();
      c.moveTo(70, y + 0.5);
      c.lineTo(w - 20, y + 0.5);
      c.stroke();
    }

    // red margin line
    c.strokeStyle = "rgba(190,60,60,0.45)";
    c.beginPath();
    c.moveTo(46, 10);
    c.lineTo(46, h - 10);
    c.stroke();

    // spiral binding holes down the left edge
    c.fillStyle = "rgba(40,35,25,0.55)";
    for (let y = 24; y < h; y += 30) {
      c.beginPath();
      c.arc(16, y, 6, 0, Math.PI * 2);
      c.fill();
    }

    // dog-ear fold, bottom-right
    const fold = 34;
    c.fillStyle = "rgba(210,196,160,0.9)";
    c.beginPath();
    c.moveTo(w - fold, h);
    c.lineTo(w, h);
    c.lineTo(w, h - fold);
    c.closePath();
    c.fill();
    c.strokeStyle = "rgba(120,105,75,0.6)";
    c.beginPath();
    c.moveTo(w - fold, h);
    c.lineTo(w, h - fold);
    c.stroke();

    return off;
  }

  function drawArrowhead(ctx, x1, y1, x2, y2, color) {
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const size = 10;
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - size * Math.cos(angle - Math.PI / 6), y2 - size * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(x2 - size * Math.cos(angle + Math.PI / 6), y2 - size * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  // draws whatever `strokeOrFill` does twice, with a tiny relative offset
  // the second time — a cheap double-inked-pencil look.
  function sketchy(ctx, draw) {
    draw(1);
    ctx.globalAlpha *= 0.45;
    ctx.save();
    ctx.translate(0.8, -0.6);
    draw(0.9);
    ctx.restore();
  }

  function drawElement(ctx, el, t, pageIndex) {
    const p = entranceProgress(el, t);
    if (p <= 0) return;
    const { type, props } = el;
    const color = props.color || INK;
    const scale = pulseScale(el, t);
    const jitter = jitterFor(el.id, pageIndex);

    ctx.save();
    ctx.globalAlpha = Math.min(1, Math.max(0, p));
    ctx.translate(jitter.dx, jitter.dy);
    ctx.rotate(jitter.rot);

    switch (type) {
      case "text": {
        const x = el.enter.style === "slide" ? lerp(props.x - 40, props.x, p) : props.x;
        ctx.translate(x, props.y);
        ctx.scale(scale, scale);
        ctx.font = `${props.fontSize || 28}px "Patrick Hand", cursive`;
        ctx.fillStyle = color;
        ctx.textAlign = props.align || "left";
        ctx.textBaseline = "middle";
        ctx.fillText(props.content || "", 0, 0);
        break;
      }
      case "circle": {
        ctx.translate(props.x, props.y);
        ctx.scale(scale, scale);
        sketchy(ctx, () => {
          ctx.beginPath();
          ctx.arc(0, 0, props.r || 20, 0, Math.PI * 2);
          if (props.fill) {
            ctx.fillStyle = color;
            ctx.fill();
          } else {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2.5;
            ctx.stroke();
          }
        });
        break;
      }
      case "rect": {
        const cx = props.x + (props.w || 0) / 2;
        const cy = props.y + (props.h || 0) / 2;
        ctx.translate(cx, cy);
        ctx.scale(scale, scale);
        ctx.translate(-cx, -cy);
        sketchy(ctx, () => {
          if (props.fill) {
            ctx.fillStyle = color;
            ctx.fillRect(props.x, props.y, props.w || 0, props.h || 0);
          } else {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2.5;
            ctx.strokeRect(props.x, props.y, props.w || 0, props.h || 0);
          }
        });
        break;
      }
      case "line":
      case "arrow": {
        const drawP = el.enter.style === "draw" ? p : 1;
        const ex = lerp(props.x, props.x2, drawP);
        const ey = lerp(props.y, props.y2, drawP);
        sketchy(ctx, () => {
          ctx.strokeStyle = color;
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(props.x, props.y);
          ctx.lineTo(ex, ey);
          ctx.stroke();
          if (type === "arrow" && drawP > 0.05) {
            drawArrowhead(ctx, props.x, props.y, ex, ey, color);
          }
        });
        break;
      }
      case "polygon": {
        const pts = props.points || [];
        if (pts.length < 2) break;
        const drawP = el.enter.style === "draw" ? p : 1;
        const shown = el.enter.style === "draw"
          ? Math.max(2, Math.round(pts.length * drawP))
          : pts.length;
        sketchy(ctx, () => {
          ctx.beginPath();
          ctx.moveTo(pts[0].x, pts[0].y);
          for (let i = 1; i < shown; i++) ctx.lineTo(pts[i].x, pts[i].y);
          if (shown === pts.length && el.enter.style !== "draw") ctx.closePath();
          if (props.fill) {
            ctx.fillStyle = color;
            ctx.fill();
          } else {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2.5;
            ctx.stroke();
          }
        });
        break;
      }
    }
    ctx.restore();
  }

  window.startScene = function startScene(ctx, canvas, scene) {
    if (currentFrame) cancelAnimationFrame(currentFrame);
    if (!paperLayer || paperLayer.width !== canvas.width || paperLayer.height !== canvas.height) {
      paperLayer = buildPaperLayer(canvas.width, canvas.height);
    }
    const start = performance.now();
    const duration = Math.max(1, scene.duration || 15);

    function frame(now) {
      const raw = ((now - start) / 1000) % duration;
      const pageIndex = Math.floor(raw * PAGE_FPS);
      const t = pageIndex / PAGE_FPS; // stepped time: the actual flipbook look

      ctx.drawImage(paperLayer, 0, 0);
      for (const el of scene.elements || []) drawElement(ctx, el, t, pageIndex);
      currentFrame = requestAnimationFrame(frame);
    }
    currentFrame = requestAnimationFrame(frame);
  };
})();
