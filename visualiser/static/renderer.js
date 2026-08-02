// Interprets a scene spec (see server.py SCENE_SCHEMA) and animates it live
// on a canvas via requestAnimationFrame. No pre-rendering, no export —
// t is real elapsed time, and the whole scene loops every `duration` seconds.

(function () {
  let currentFrame = null;

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

  function drawElement(ctx, el, t) {
    const p = entranceProgress(el, t);
    if (p <= 0) return;
    const { type, props } = el;
    const color = props.color || "#e6e8ee";
    const scale = pulseScale(el, t);

    ctx.save();
    ctx.globalAlpha = Math.min(1, Math.max(0, p));

    switch (type) {
      case "text": {
        const x = el.enter.style === "slide" ? lerp(props.x - 40, props.x, p) : props.x;
        ctx.translate(x, props.y);
        ctx.scale(scale, scale);
        ctx.font = `${props.fontSize || 28}px system-ui, sans-serif`;
        ctx.fillStyle = color;
        ctx.textAlign = props.align || "left";
        ctx.textBaseline = "middle";
        ctx.fillText(props.content || "", 0, 0);
        break;
      }
      case "circle": {
        ctx.translate(props.x, props.y);
        ctx.scale(scale, scale);
        ctx.beginPath();
        ctx.arc(0, 0, props.r || 20, 0, Math.PI * 2);
        if (props.fill) {
          ctx.fillStyle = color;
          ctx.fill();
        } else {
          ctx.strokeStyle = color;
          ctx.lineWidth = 3;
          ctx.stroke();
        }
        break;
      }
      case "rect": {
        const cx = props.x + (props.w || 0) / 2;
        const cy = props.y + (props.h || 0) / 2;
        ctx.translate(cx, cy);
        ctx.scale(scale, scale);
        ctx.translate(-cx, -cy);
        if (props.fill) {
          ctx.fillStyle = color;
          ctx.fillRect(props.x, props.y, props.w || 0, props.h || 0);
        } else {
          ctx.strokeStyle = color;
          ctx.lineWidth = 3;
          ctx.strokeRect(props.x, props.y, props.w || 0, props.h || 0);
        }
        break;
      }
      case "line":
      case "arrow": {
        const drawP = el.enter.style === "draw" ? p : 1;
        const ex = lerp(props.x, props.x2, drawP);
        const ey = lerp(props.y, props.y2, drawP);
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(props.x, props.y);
        ctx.lineTo(ex, ey);
        ctx.stroke();
        if (type === "arrow" && drawP > 0.05) {
          drawArrowhead(ctx, props.x, props.y, ex, ey, color);
        }
        break;
      }
      case "polygon": {
        const pts = props.points || [];
        if (pts.length < 2) break;
        const drawP = el.enter.style === "draw" ? p : 1;
        const shown = el.enter.style === "draw"
          ? Math.max(2, Math.round(pts.length * drawP))
          : pts.length;
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < shown; i++) ctx.lineTo(pts[i].x, pts[i].y);
        if (shown === pts.length && el.enter.style !== "draw") ctx.closePath();
        if (props.fill) {
          ctx.fillStyle = color;
          ctx.fill();
        } else {
          ctx.strokeStyle = color;
          ctx.lineWidth = 3;
          ctx.stroke();
        }
        break;
      }
    }
    ctx.restore();
  }

  window.startScene = function startScene(ctx, canvas, scene) {
    if (currentFrame) cancelAnimationFrame(currentFrame);
    const start = performance.now();
    const duration = Math.max(1, scene.duration || 15);

    function frame(now) {
      const t = ((now - start) / 1000) % duration;
      ctx.fillStyle = scene.background || "#0b0f19";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      for (const el of scene.elements || []) drawElement(ctx, el, t);
      currentFrame = requestAnimationFrame(frame);
    }
    currentFrame = requestAnimationFrame(frame);
  };
})();
