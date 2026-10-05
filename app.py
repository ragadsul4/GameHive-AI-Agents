
import base64
import html
import mimetypes
import textwrap
import time
import traceback
from functools import lru_cache
from pathlib import Path

import streamlit as st

from workflow.gamehive_graph import run_gamehive_graph


BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"

st.set_page_config(
    page_title="GameHive",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# HELPERS
# ============================================================

def esc(value):
    return html.escape(str(value))


def esc_br(value):
    """Escape + keep line breaks (used for chat bubbles)."""
    return esc(value).replace("\n", "<br>")


def clip(value, limit):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render_html(content):
    st.html(textwrap.dedent(content).strip())


@lru_cache(maxsize=None)
def _read_asset(filename):
    path = ASSET_DIR / filename

    if not path.exists():
        return None

    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")

    return f"data:{mime};base64,{encoded}"


def asset_uri(filename):
    uri = _read_asset(filename)

    if uri is None:
        st.error(
            f"Missing image: {filename}\n\n"
            f"Expected here: {ASSET_DIR / filename}\n\n"
            "Keep the assets folder beside app.py."
        )
        st.stop()

    return uri


def embed_html(content, height):
    """Embed a self-contained HTML page (needed for the 3D scene).

    Newer Streamlit versions replace `components.v1.html` with `st.iframe`,
    so use whichever one this install provides.
    """
    content = content.strip()

    if hasattr(st, "iframe"):
        return st.iframe(content, height=max(int(height), 1))

    import streamlit.components.v1 as components

    return components.html(content, height=height, scrolling=False)


def as_list(value):
    if value is None:
        return []

    try:
        return list(value)
    except TypeError:
        return []


def attr(obj, name, default=""):
    value = getattr(obj, name, default)
    return default if value is None else value


def go(page_name):
    st.query_params["page"] = page_name
    st.rerun()

# ============================================================
# 3D INTRO SCENE  (Three.js, runs inside an iframe component)
# ============================================================
# A procedural console-style mascot ("HIVE"): no external model files.
# Its head follows the cursor anywhere on the page.

INTRO_3D_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{--gold:#cda56e;--gold2:#efd2a4;--cyan:#5ee7ff;
--head:'Orbitron','Rajdhani','Segoe UI',sans-serif;--body:'Rajdhani','Segoe UI',system-ui,sans-serif;}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;height:100%;overflow:hidden;color:#f2eee6;font-family:var(--body);background:#05060a}
body{background:
  radial-gradient(ellipse at 74% 46%,rgba(94,231,255,.17),transparent 48%),
  radial-gradient(ellipse at 14% 92%,rgba(205,165,110,.16),transparent 52%),
  linear-gradient(180deg,#080a10,#05060a);position:relative}
.grid{position:absolute;inset:0;pointer-events:none;
  background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);
  background-size:56px 56px;
  -webkit-mask-image:radial-gradient(ellipse at 72% 52%,#000 6%,transparent 70%);
  mask-image:radial-gradient(ellipse at 72% 52%,#000 6%,transparent 70%)}
canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.scan{position:absolute;inset:0;pointer-events:none;opacity:.6;
  background:repeating-linear-gradient(0deg,rgba(255,255,255,.028) 0 1px,transparent 1px 3px)}
.vignette{position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(ellipse at center,transparent 52%,rgba(0,0,0,.7))}
.top{position:absolute;top:0;left:0;right:0;height:78px;padding:0 6vw;display:flex;align-items:center;
  justify-content:space-between;pointer-events:none;z-index:5}
.brand{font-family:var(--head);font-weight:900;font-size:15px;letter-spacing:.34em}
.brand small{display:block;margin-top:5px;font-family:var(--body);font-weight:600;font-size:11px;
  letter-spacing:.3em;color:var(--gold2)}
.status{font-family:var(--head);font-size:11px;letter-spacing:.22em;color:rgba(255,255,255,.7);
  display:flex;align-items:center;gap:10px}
.status i{width:8px;height:8px;border-radius:50%;background:#4be3a4;box-shadow:0 0 10px #4be3a4;animation:pulse 1.6s infinite}
@keyframes pulse{50%{opacity:.35}}
.copy{position:absolute;left:6vw;top:50%;transform:translateY(-62%);width:min(620px,46vw);z-index:5;pointer-events:none}
.eyebrow{font-family:var(--head);font-size:12px;letter-spacing:.34em;color:var(--gold2);margin-bottom:18px;
  display:flex;align-items:center;gap:12px}
.eyebrow::after{content:"";height:1px;width:70px;background:linear-gradient(90deg,var(--gold),transparent)}
h1{font-family:var(--head);font-weight:900;font-size:clamp(2.3rem,5vw,5rem);line-height:.98;letter-spacing:-.01em;
  text-shadow:0 0 40px rgba(94,231,255,.18)}
h1 span{display:block;background:linear-gradient(90deg,var(--gold2),var(--gold) 55%,#fff1d6);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.copy p{margin-top:22px;max-width:500px;font-size:19px;line-height:1.55;color:rgba(255,255,255,.72);font-weight:500}
.chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}
.chips b{font-family:var(--head);font-size:11px;letter-spacing:.2em;padding:9px 14px;
  border:1px solid rgba(239,210,164,.35);background:rgba(16,14,12,.6);color:var(--gold2);font-weight:700}
.hint{position:absolute;right:6vw;bottom:5vh;z-index:5;pointer-events:none;text-align:right;
  font-family:var(--head);font-size:10px;letter-spacing:.22em;line-height:2;color:rgba(255,255,255,.42)}
.say{position:absolute;left:50%;top:20%;z-index:6;transform:translate(-50%,-100%) scale(.85);opacity:0;
  transition:opacity .25s,transform .25s;pointer-events:none;background:#f4f1ea;color:#0b0b0b;
  font-family:var(--body);font-weight:700;font-size:18px;padding:11px 18px;border-radius:16px;white-space:nowrap;
  box-shadow:0 8px 30px rgba(0,0,0,.45)}
.say::after{content:"";position:absolute;left:50%;bottom:-8px;width:16px;height:16px;background:#f4f1ea;
  transform:translateX(-50%) rotate(45deg);border-radius:3px}
.say.show{opacity:1;transform:translate(-50%,-100%) scale(1)}
.fallback{display:none;position:absolute;right:14vw;top:50%;transform:translateY(-50%);width:170px;height:150px;
  border-radius:60px;background:linear-gradient(145deg,#f4f6fa,#aab3c4);align-items:center;justify-content:center;
  gap:28px;z-index:4}
.fallback i{display:block;width:22px;height:34px;border-radius:12px;background:var(--cyan);box-shadow:0 0 18px var(--cyan)}
@media (max-width:900px){
  .copy{top:13vh;transform:none;width:88vw}
  .copy p{font-size:17px}
  .hint{display:none}
  .chips{display:none}
  .status{display:none}
}
</style>
</head>
<body>
<div class="grid"></div>
<canvas id="c"></canvas>
<div class="scan"></div>
<div class="vignette"></div>
<div id="say" class="say"></div>

<div class="top">
  <div class="brand">GAMEHIVE<small>WORLDS BEYOND IMAGINATION</small></div>
  <div class="status"><i></i>PLAYER 01 · READY</div>
</div>

<div class="copy">
  <div class="eyebrow">▶ NEW GAME</div>
  <h1>CREATE GAMES<span>THAT MATTER.</span></h1>
  <p>From one idea to a complete playable concept. Story, characters, gameplay and level design,
     built by one autonomous design system with culturally grounded facts.</p>
  <div class="chips"><b>STORY ENGINE</b><b>WORLD ENGINE</b><b>GAMEPLAY ENGINE</b></div>
</div>

<div class="hint">MOVE YOUR CURSOR · HIVE IS WATCHING<br>CLICK HIVE TO SAY HI</div>
<div id="fallback" class="fallback"><i></i><i></i></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
  'use strict';

  var fallback = document.getElementById('fallback');
  if (typeof THREE === 'undefined') { fallback.style.display = 'flex'; return; }

  var canvas = document.getElementById('c');
  var sayEl = document.getElementById('say');
  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
  } catch (err) { fallback.style.display = 'flex'; return; }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.outputEncoding = THREE.sRGBEncoding;

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function lerp(a, b, k) { return a + (b - a) * k; }

  // ---------- fit the iframe to the browser viewport ----------
  function fit() {
    try {
      var fe = window.frameElement;
      if (fe && window.parent) {
        fe.style.height = Math.max(520, window.parent.innerHeight) + 'px';
        fe.style.width = '100%';
        fe.style.display = 'block';
      }
    } catch (e) {}
  }
  fit();
  try { window.parent.addEventListener('resize', fit); } catch (e) {}

  // ---------- scene / camera / lights ----------
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(0, 0.4, 11.5);
  camera.lookAt(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0xbfd8ff, 0x1a1208, 0.85));
  var key = new THREE.DirectionalLight(0xffffff, 1.15);
  key.position.set(3, 5, 6);
  scene.add(key);
  var rimGold = new THREE.PointLight(0xcda56e, 1.7, 22);
  rimGold.position.set(-4, 2, -3);
  scene.add(rimGold);
  var rimCyan = new THREE.PointLight(0x5ee7ff, 1.9, 22);
  rimCyan.position.set(4, 1, -2);
  scene.add(rimCyan);
  var faceFill = new THREE.PointLight(0x5ee7ff, 0.5, 8);
  faceFill.position.set(0, 1.6, 3.2);
  scene.add(faceFill);

  // ---------- materials ----------
  var mWhite = new THREE.MeshStandardMaterial({ color: 0xeef1f7, roughness: 0.35, metalness: 0.15 });
  var mDark = new THREE.MeshStandardMaterial({ color: 0x10131c, roughness: 0.5, metalness: 0.4 });
  var mVisor = new THREE.MeshStandardMaterial({ color: 0x06080e, roughness: 0.12, metalness: 0.55 });
  var mGold = new THREE.MeshStandardMaterial({ color: 0xcda56e, roughness: 0.3, metalness: 0.85, emissive: 0x3a2a10 });
  var mCyan = new THREE.MeshBasicMaterial({ color: 0x6de9ff });
  var mGoldGlow = new THREE.MeshBasicMaterial({ color: 0xffd89a });

  function mk(geo, mat, x, y, z, sx, sy, sz) {
    var m = new THREE.Mesh(geo, mat);
    m.position.set(x || 0, y || 0, z || 0);
    if (sx !== undefined) m.scale.set(sx, sy, sz);
    return m;
  }

  // ---------- character ----------
  var world = new THREE.Group();
  scene.add(world);
  var hive = new THREE.Group();
  world.add(hive);
  var body = new THREE.Group();
  hive.add(body);

  // torso
  body.add(mk(new THREE.SphereGeometry(1, 40, 32), mWhite, 0, -0.35, 0, 0.78, 0.86, 0.66));
  body.add(mk(new THREE.SphereGeometry(1, 32, 24), mDark, 0, -0.2, 0.58, 0.5, 0.42, 0.2));
  var core = mk(new THREE.SphereGeometry(1, 24, 16), mGoldGlow, 0, -0.2, 0.76, 0.15, 0.15, 0.06);
  body.add(core);
  body.add(mk(new THREE.CylinderGeometry(0.22, 0.26, 0.34, 24), mDark, 0, 0.52, 0));

  // hover base + thruster
  var base = mk(new THREE.ConeGeometry(0.55, 0.9, 32), mDark, 0, -1.5, 0);
  base.rotation.x = Math.PI;
  body.add(base);
  var belt = mk(new THREE.TorusGeometry(0.6, 0.05, 12, 48), mGold, 0, -1.12, 0);
  belt.rotation.x = Math.PI / 2;
  body.add(belt);
  var flameMat = new THREE.MeshBasicMaterial({ color: 0x5ee7ff, transparent: true, opacity: 0.75,
    blending: THREE.AdditiveBlending, depthWrite: false });
  var flame = mk(new THREE.ConeGeometry(0.3, 0.95, 24), flameMat, 0, -2.4, 0);
  flame.rotation.x = Math.PI;
  body.add(flame);
  var flameCoreMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85,
    blending: THREE.AdditiveBlending, depthWrite: false });
  var flameCore = mk(new THREE.ConeGeometry(0.14, 0.6, 16), flameCoreMat, 0, -2.2, 0);
  flameCore.rotation.x = Math.PI;
  body.add(flameCore);

  // arms
  function makeArm(side) {
    var g = new THREE.Group();
    g.position.set(side * 0.98, -0.12, 0);
    g.add(mk(new THREE.SphereGeometry(0.3, 24, 20), mWhite, 0, 0, 0));
    g.add(mk(new THREE.CylinderGeometry(0.12, 0.1, 0.62, 16), mDark, 0, -0.42, 0));
    var hand = mk(new THREE.SphereGeometry(0.22, 24, 20), mWhite, 0, -0.86, 0);
    g.add(hand);
    var ring = mk(new THREE.TorusGeometry(0.2, 0.03, 10, 24), mGold, 0, -0.68, 0);
    ring.rotation.x = Math.PI / 2;
    g.add(ring);
    g.rotation.z = side * 0.35;
    body.add(g);
    return g;
  }
  var armL = makeArm(-1);
  var armR = makeArm(1);

  // head
  var headPivot = new THREE.Group();
  headPivot.position.set(0, 1.5, 0);
  hive.add(headPivot);
  headPivot.add(mk(new THREE.SphereGeometry(1, 56, 44), mWhite, 0, 0, 0, 1.12, 0.96, 1.02));
  headPivot.add(mk(new THREE.SphereGeometry(1, 48, 36), mVisor, 0, -0.02, 0.68, 0.96, 0.66, 0.42));

  var eyes = new THREE.Group();
  headPivot.add(eyes);
  var eyeBaseY = 0.19;
  var eyeL = mk(new THREE.SphereGeometry(1, 20, 16), mCyan, -0.36, 0.06, 1.06, 0.13, eyeBaseY, 0.05);
  var eyeR = mk(new THREE.SphereGeometry(1, 20, 16), mCyan, 0.36, 0.06, 1.06, 0.13, eyeBaseY, 0.05);
  eyes.add(eyeL);
  eyes.add(eyeR);

  var mouth = mk(new THREE.TorusGeometry(0.11, 0.022, 8, 24, Math.PI), mCyan, 0, -0.2, 1.08);
  mouth.rotation.z = Math.PI;
  headPivot.add(mouth);

  function makeEar(side) {
    var g = new THREE.Group();
    var disc = mk(new THREE.CylinderGeometry(0.25, 0.25, 0.22, 32), mDark, 0, 0, 0);
    disc.rotation.z = Math.PI / 2;
    g.add(disc);
    var ring = mk(new THREE.TorusGeometry(0.2, 0.03, 10, 32), mGold, side * 0.12, 0, 0);
    ring.rotation.y = Math.PI / 2;
    g.add(ring);
    var dot = mk(new THREE.CylinderGeometry(0.11, 0.11, 0.02, 20), mCyan, side * 0.115, 0, 0);
    dot.rotation.z = Math.PI / 2;
    g.add(dot);
    g.position.set(side * 1.13, -0.02, 0);
    headPivot.add(g);
    return g;
  }
  makeEar(-1);
  makeEar(1);

  var antenna = new THREE.Group();
  antenna.position.set(0, 0.92, 0);
  headPivot.add(antenna);
  antenna.add(mk(new THREE.CylinderGeometry(0.03, 0.045, 0.5, 12), mDark, 0, 0.25, 0));
  var tip = mk(new THREE.SphereGeometry(0.12, 20, 16), mGoldGlow, 0, 0.58, 0);
  antenna.add(tip);

  // ---------- floor rings ----------
  var floor = new THREE.Group();
  floor.position.y = -3.05;
  world.add(floor);
  var ring1 = mk(new THREE.TorusGeometry(1.6, 0.022, 12, 96), mGold, 0, 0, 0);
  ring1.rotation.x = Math.PI / 2;
  floor.add(ring1);
  var ring2 = mk(new THREE.TorusGeometry(2.3, 0.014, 12, 96), new THREE.MeshBasicMaterial({ color: 0x5ee7ff, transparent: true, opacity: 0.6 }), 0, 0, 0);
  ring2.rotation.x = Math.PI / 2;
  floor.add(ring2);

  var glowCanvas = document.createElement('canvas');
  glowCanvas.width = glowCanvas.height = 128;
  var gctx = glowCanvas.getContext ? glowCanvas.getContext('2d') : null;
  if (gctx) {
    var grad = gctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, 'rgba(94,231,255,.55)');
    grad.addColorStop(0.5, 'rgba(94,231,255,.16)');
    grad.addColorStop(1, 'rgba(94,231,255,0)');
    gctx.fillStyle = grad;
    gctx.fillRect(0, 0, 128, 128);
    var glowTex = new THREE.CanvasTexture(glowCanvas);
    var disc = new THREE.Mesh(new THREE.CircleGeometry(2.8, 48),
      new THREE.MeshBasicMaterial({ map: glowTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    disc.rotation.x = -Math.PI / 2;
    disc.position.y = 0.01;
    floor.add(disc);
  }

  // ---------- floating console-style symbols ----------
  function symMat(color) {
    return new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.55, roughness: 0.4, metalness: 0.2 });
  }
  function polyRing(points, color) {
    var pts = points.map(function (p) { return new THREE.Vector3(p[0], p[1], 0); });
    var curve = new THREE.CatmullRomCurve3(pts, true, 'catmullrom', 0.05);
    return new THREE.Mesh(new THREE.TubeGeometry(curve, 96, 0.035, 8, true), symMat(color));
  }
  var tri = [];
  for (var i = 0; i < 3; i++) {
    var a = Math.PI / 2 + i * Math.PI * 2 / 3;
    tri.push([Math.cos(a) * 0.34, Math.sin(a) * 0.34]);
  }
  var symbols = [];
  var symTriangle = polyRing(tri, 0x3fe0a5);
  var symCircle = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.036, 10, 48), symMat(0xff5a6e));
  var symCross = new THREE.Group();
  var barA = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.07, 0.07), symMat(0x5b8cff));
  var barB = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.07, 0.07), symMat(0x5b8cff));
  barA.rotation.z = Math.PI / 4;
  barB.rotation.z = -Math.PI / 4;
  symCross.add(barA);
  symCross.add(barB);
  var symSquare = polyRing([[-0.26, -0.26], [0.26, -0.26], [0.26, 0.26], [-0.26, 0.26]], 0xff8fd6);
  symbols.push(symTriangle, symCircle, symCross, symSquare);
  var symY = [1.2, -0.5, 0.8, -1.2];
  symbols.forEach(function (s) { world.add(s); });

  // ---------- particles ----------
  var PCOUNT = 220;
  var pPos = new Float32Array(PCOUNT * 3);
  var pSpeed = new Float32Array(PCOUNT);
  for (var p = 0; p < PCOUNT; p++) {
    pPos[p * 3] = (Math.random() - 0.5) * 16;
    pPos[p * 3 + 1] = (Math.random() - 0.5) * 8;
    pPos[p * 3 + 2] = -3 + Math.random() * 6;
    pSpeed[p] = 0.05 + Math.random() * 0.22;
  }
  var pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
  var particles = new THREE.Points(pGeo, new THREE.PointsMaterial({ color: 0xefd2a4, size: 0.05,
    transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(particles);

  // ---------- layout ----------
  var W = 0, H = 0;
  var baseX = 0, baseY = 0, baseS = 0.74;
  function layout() {
    W = window.innerWidth || 1;
    H = window.innerHeight || 1;
    renderer.setSize(W, H, false);
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
    var visH = 2 * camera.position.z * Math.tan(camera.fov * Math.PI / 360);
    var visW = visH * camera.aspect;
    if (camera.aspect > 1.1) { baseX = visW * 0.235; baseY = -0.1; baseS = 0.74; }
    else { baseX = 0; baseY = -visH * 0.16; baseS = 0.56; }
    world.position.set(baseX, baseY, 0);
    world.scale.setScalar(baseS);
  }
  layout();

  // ---------- pointer tracking ----------
  var mouse = { x: 0, y: 0, has: false, t: 0 };
  function setPointer(x, y) { mouse.x = x; mouse.y = y; mouse.has = true; mouse.t = performance.now(); }
  window.addEventListener('mousemove', function (e) { setPointer(e.clientX, e.clientY); }, { passive: true });
  window.addEventListener('touchmove', function (e) {
    if (e.touches && e.touches[0]) setPointer(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  document.addEventListener('mouseleave', function () { mouse.has = false; });
  try {
    var pw = window.parent, fe = window.frameElement;
    if (pw && pw !== window && fe) {
      // the cursor is tracked over the WHOLE page, not only over this iframe
      pw.addEventListener('mousemove', function (e) {
        var r = fe.getBoundingClientRect();
        setPointer(e.clientX - r.left, e.clientY - r.top);
      }, { passive: true });
      pw.document.addEventListener('mouseleave', function () { mouse.has = false; });
    }
  } catch (err) {}

  // ---------- interaction ----------
  var sayTimer = null;
  function say(text, ms) {
    sayEl.textContent = text;
    sayEl.classList.add('show');
    clearTimeout(sayTimer);
    sayTimer = setTimeout(function () { sayEl.classList.remove('show'); }, ms || 2600);
  }
  var lines = ['Ready when you are, player!', 'Press START to begin!', 'Got an idea? Let us build a world.',
    'Hehe, that tickles!', 'Every great game starts with one idea.'];
  var lineIdx = 0, jumpT = 0, jumpY = 0, waveT = 0, happy = 0;
  var raycaster = new THREE.Raycaster();
  var ndc = new THREE.Vector2();
  canvas.addEventListener('pointerdown', function (e) {
    var r = canvas.getBoundingClientRect();
    ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    raycaster.setFromCamera(ndc, camera);
    if (raycaster.intersectObject(hive, true).length) {
      jumpT = 0.0001; waveT = 0.0001; happy = 1;
      say(lines[lineIdx++ % lines.length], 2600);
    }
  });
  setTimeout(function () { say('Hi player! Press START to begin.', 4200); }, 1400);

  // ---------- animation ----------
  var tmp = new THREE.Vector3();
  var yaw = 0, pitch = 0, eyeX = 0, eyeY = 0;
  var t = 0, last = 0, blinkT = 2.5, blinking = 0;

  function tick(now) {
    window.requestAnimationFrame(tick);
    var dt = last ? Math.min(0.05, (now - last) / 1000) : 0.016;
    last = now;
    t += dt;
    if (window.innerWidth !== W || window.innerHeight !== H) layout();

    // where is the head on screen?
    headPivot.getWorldPosition(tmp);
    tmp.project(camera);
    var hx = (tmp.x * 0.5 + 0.5) * W;
    var hy = (-tmp.y * 0.5 + 0.5) * H;

    var idle = !mouse.has || (performance.now() - mouse.t > 5000);
    var nx, ny;
    if (idle) {
      nx = Math.sin(t * 0.6) * 0.35;
      ny = Math.sin(t * 0.4) * 0.12;
    } else {
      nx = clamp((mouse.x - hx) / (W * 0.32), -1, 1);
      ny = clamp((mouse.y - hy) / (H * 0.32), -1, 1);
    }
    var k = 1 - Math.exp(-dt * 9);
    yaw = lerp(yaw, nx * 0.95, k);
    pitch = lerp(pitch, ny * 0.5, k);
    headPivot.rotation.y = yaw;
    headPivot.rotation.x = pitch;
    body.rotation.y = yaw * 0.25;
    world.rotation.y = yaw * 0.08;
    eyeX = lerp(eyeX, nx * 0.06, k);
    eyeY = lerp(eyeY, -ny * 0.04, k);
    eyes.position.x = eyeX;
    eyes.position.y = eyeY;

    // blink + happy squint
    blinkT -= dt;
    if (blinkT <= 0 && blinking <= 0) { blinking = 0.13; blinkT = 2.5 + Math.random() * 3; }
    if (blinking > 0) blinking -= dt;
    happy = Math.max(0, happy - dt * 0.6);
    var lid = blinking > 0 ? 0.08 : 1;
    eyeL.scale.y = eyeR.scale.y = eyeBaseY * lid * (1 - 0.35 * happy);
    mouth.scale.set(1 + happy * 0.6, 1 + happy * 0.9, 1);

    // jump + wave
    if (jumpT > 0) {
      jumpT += dt;
      var pr = jumpT / 0.7;
      if (pr >= 1) { jumpT = 0; jumpY = 0; } else { jumpY = Math.sin(pr * Math.PI) * 0.7; }
    }
    var armLTarget = -0.35 + Math.sin(t * 1.2) * 0.05;
    if (waveT > 0) {
      waveT += dt;
      var up = Math.sin(clamp(waveT / 0.35, 0, 1) * Math.PI / 2) * (1 - clamp((waveT - 1.8) / 0.4, 0, 1));
      armLTarget = lerp(armLTarget, -2.55 + Math.sin(t * 16) * 0.3, up);
      if (waveT > 2.2) waveT = 0;
    }
    var ka = 1 - Math.exp(-dt * 14);
    armL.rotation.z = lerp(armL.rotation.z, armLTarget, ka);
    armR.rotation.z = lerp(armR.rotation.z, 0.35 - Math.sin(t * 1.2 + 1) * 0.05, ka);

    // idle float
    hive.position.y = Math.sin(t * 1.6) * 0.12 + jumpY;
    body.rotation.z = Math.sin(t * 1.1) * 0.03;
    antenna.rotation.z = Math.sin(t * 2.4) * 0.22 - yaw * 0.15;
    antenna.rotation.x = Math.cos(t * 1.9) * 0.12;
    var pulse = 0.85 + Math.sin(t * 3) * 0.15;
    tip.scale.setScalar(pulse);
    core.scale.set(0.15 * pulse, 0.15 * pulse, 0.06);
    var fl = 1 + Math.sin(t * 22) * 0.12 + Math.sin(t * 13) * 0.08;
    flame.scale.set(1, fl, 1);
    flameCore.scale.set(1, fl * 1.05, 1);
    flameMat.opacity = 0.65 + Math.sin(t * 17) * 0.1;
    ring1.rotation.z = t * 0.5;
    ring2.scale.setScalar(1 + Math.sin(t * 1.4) * 0.04);

    // orbiting symbols
    for (var s = 0; s < symbols.length; s++) {
      var ang = t * 0.42 + s * Math.PI / 2;
      symbols[s].position.set(Math.cos(ang) * 2.7, symY[s] + Math.sin(t * 1.2 + s) * 0.3, Math.sin(ang) * 1.7);
      symbols[s].rotation.x = t * 0.8 + s;
      symbols[s].rotation.y = t * 1.1 + s * 2;
    }

    // particles drifting up
    var arr = pGeo.attributes.position.array;
    for (var q = 0; q < PCOUNT; q++) {
      arr[q * 3 + 1] += pSpeed[q] * dt;
      if (arr[q * 3 + 1] > 4) arr[q * 3 + 1] = -4;
    }
    pGeo.attributes.position.needsUpdate = true;

    // speech bubble follows the head
    tmp.set(0, 3.7, 0);
    hive.localToWorld(tmp);
    tmp.project(camera);
    var sx = (tmp.x * 0.5 + 0.5) * W;
    var sy = (-tmp.y * 0.5 + 0.5) * H;
    sayEl.style.left = clamp(sx, 150, Math.max(150, W - 150)) + 'px';
    sayEl.style.top = Math.max(sy, 70) + 'px';

    renderer.render(scene, camera);
  }
  window.requestAnimationFrame(tick);
})();
</script>
</body>
</html>
"""

# ============================================================
# STYLE
# ============================================================

BASE_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@500;600;700&display=swap');

:root {
    --bg: #05060a;
    --panel: #0b0d14;
    --panel2: #10131c;
    --text: #f2eee6;
    --muted: #9aa0ad;
    --gold: #cda56e;
    --gold2: #efd2a4;
    --cyan: #5ee7ff;
    --green: #4be3a4;
    --pink: #ff6fae;
    --line: rgba(255,255,255,.09);
    --line2: rgba(239,210,164,.24);
    --head: 'Orbitron', 'Rajdhani', 'Segoe UI', sans-serif;
    --body: 'Rajdhani', 'Segoe UI', system-ui, sans-serif;
}

* { box-sizing: border-box; }

html, body, .stApp {
    background: var(--bg);
    color: var(--text);
    font-family: var(--body);
    overflow-x: hidden;
}

.block-container {
    max-width: 100%;
    padding: 0 !important;
}

[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stSidebar"],
#MainMenu,
footer {
    display: none !important;
}

@keyframes blink { 0%,92%,100% { transform: scaleY(1); } 95% { transform: scaleY(.1); } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulseGlow { 50% { opacity: .45; } }

/* HIVE face (CSS avatar, same look as the 3D mascot) */
.bot-face {
    width: 46px; height: 46px; border-radius: 15px; position: relative; display: inline-block; flex: none;
    background: linear-gradient(145deg, #f4f6fa, #b3bbcb);
    box-shadow: 0 0 20px rgba(94,231,255,.35);
}
.bot-face::before {
    content: ""; position: absolute; left: 6px; right: 6px; top: 12px; height: 23px;
    border-radius: 11px; background: #070911;
}
.bot-face::after {
    content: ""; position: absolute; top: -9px; left: 50%; width: 2px; height: 9px;
    background: #b3bbcb; box-shadow: 0 -3px 0 2px var(--gold);
}
.bot-face i {
    position: absolute; top: 19px; width: 7px; height: 11px; border-radius: 4px; z-index: 2;
    background: var(--cyan); box-shadow: 0 0 9px var(--cyan); animation: blink 4.5s infinite;
}
.bot-face i:nth-child(1) { left: 13px; }
.bot-face i:nth-child(2) { right: 13px; }
.bot-face.big { width: 74px; height: 74px; border-radius: 24px; }
.bot-face.big::before { left: 9px; right: 9px; top: 19px; height: 37px; border-radius: 17px; }
.bot-face.big i { top: 31px; width: 11px; height: 18px; border-radius: 6px; }
.bot-face.big i:nth-child(1) { left: 21px; }
.bot-face.big i:nth-child(2) { right: 21px; }
</style>
"""


INTRO_CSS = r"""
<style>
[data-testid="stVerticalBlock"] { gap: 0 !important; }
iframe { display: block !important; border: 0 !important; }

/* native Streamlit button, floated over the 3D scene */
.st-key-start_btn {
    position: fixed !important;
    left: 6vw;
    bottom: 11vh;
    z-index: 60;
    width: auto !important;
    filter: drop-shadow(0 0 16px rgba(205,165,110,.55));
    animation: pulseGlow 2.2s ease-in-out infinite;
}
.st-key-start_btn button {
    min-width: 300px;
    min-height: 62px;
    border: 0 !important;
    border-radius: 0 !important;
    background: linear-gradient(90deg, #cda56e, #efd2a4) !important;
    clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 16px 100%, 0 calc(100% - 16px));
    transition: transform .2s ease, filter .2s ease;
}
.st-key-start_btn button:hover { transform: translateY(-2px) scale(1.02); filter: brightness(1.1); }
.st-key-start_btn button p {
    color: #0a0a0a !important;
    font-family: var(--head) !important;
    font-weight: 900 !important;
    font-size: 15px !important;
    letter-spacing: .24em !important;
}
@media (max-width: 900px) {
    .st-key-start_btn { left: 50%; transform: translateX(-50%); bottom: 6vh; }
    .st-key-start_btn button { min-width: 260px; }
}
</style>
"""


CHAT_CSS = r"""
<style>
/* ---------- page shell ---------- */
.stApp { background: var(--bg); }

.stApp::before {
    content: "";
    position: fixed; inset: 0; z-index: 0;
    background-size: cover; background-position: center;
    filter: brightness(.20) saturate(.75) blur(1px);
    transform: scale(1.04);
}
.stApp::after {
    content: "";
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(ellipse at 15% 0%, rgba(94,231,255,.10), transparent 45%),
        radial-gradient(ellipse at 90% 100%, rgba(205,165,110,.12), transparent 50%),
        linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px);
    background-size: auto, auto, 56px 56px, 56px 56px;
}
[data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {
    position: relative; z-index: 1; background: transparent !important;
}
.block-container {
    max-width: 1080px !important;
    margin: 0 auto;
    padding: 0 18px 150px !important;
}
.stApp p, .stApp li, .stMarkdown { color: var(--text); font-family: var(--body); }
.stApp p { font-size: 17px; line-height: 1.55; }

/* ---------- HUD top bar ---------- */
.hud {
    margin-top: 16px;
    padding: 14px 20px;
    display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap;
    background: linear-gradient(180deg, rgba(16,19,28,.92), rgba(9,11,17,.92));
    border: 1px solid var(--line2);
    position: relative;
    backdrop-filter: blur(10px);
}
.hud::before, .hud::after, .box::before, .box::after {
    content: ""; position: absolute; width: 14px; height: 14px; pointer-events: none;
}
.hud::before, .box::before { top: -1px; left: -1px; border-top: 2px solid var(--gold); border-left: 2px solid var(--gold); }
.hud::after, .box::after { bottom: -1px; right: -1px; border-bottom: 2px solid var(--gold); border-right: 2px solid var(--gold); }
.box { position: relative; }

.hud-brand { display: flex; align-items: center; gap: 14px;
    font-family: var(--head); font-weight: 900; letter-spacing: .3em; font-size: 15px; }
.hud-brand small { display: block; margin-top: 5px; font-family: var(--body); font-weight: 600;
    font-size: 11px; letter-spacing: .28em; color: var(--gold2); }
.hud-right { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }
.hud-chip { font-family: var(--head); font-size: 10px; letter-spacing: .2em; color: rgba(255,255,255,.7);
    display: flex; align-items: center; gap: 9px; }
.hud-chip i { width: 8px; height: 8px; border-radius: 50%; background: var(--green);
    box-shadow: 0 0 10px var(--green); animation: pulseGlow 1.6s infinite; }
.hud-xp { display: flex; align-items: center; gap: 12px; font-family: var(--head); font-size: 10px;
    letter-spacing: .18em; color: var(--gold2); }
.xp { width: 130px; height: 8px; background: rgba(255,255,255,.08); position: relative; overflow: hidden; }
.xp b { position: absolute; inset: 0 auto 0 0; background: linear-gradient(90deg, var(--gold), var(--cyan));
    box-shadow: 0 0 12px rgba(94,231,255,.6); }

/* ---------- controls (native widgets) ---------- */
div.stButton > button,
div[data-testid="stFormSubmitButton"] > button,
div.stDownloadButton > button,
div[data-testid="stPopover"] button {
    min-height: 46px;
    border-radius: 0 !important;
    border: 1px solid rgba(239,210,164,.42) !important;
    background: rgba(14,15,20,.92) !important;
    color: #f4eee5 !important;
    transition: all .2s ease;
}
div.stButton > button p,
div.stDownloadButton > button p {
    font-family: var(--head) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: .16em !important;
    text-transform: uppercase !important;
    color: #f4eee5 !important;
}
div.stButton > button:hover,
div.stDownloadButton > button:hover {
    background: rgba(205,165,110,.20) !important;
    border-color: var(--gold2) !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 22px rgba(205,165,110,.16);
}
div[data-testid="stRadio"] > div { gap: 8px; }
div[data-testid="stRadio"] label {
    background: rgba(14,15,20,.92); border: 1px solid rgba(255,255,255,.12);
    padding: 8px 16px; cursor: pointer;
}
div[data-testid="stRadio"] label:has(input:checked) {
    border-color: var(--gold2); background: rgba(205,165,110,.18);
}
div[data-testid="stRadio"] label p {
    font-family: var(--head) !important; font-size: 11px !important; letter-spacing: .16em !important;
}

/* ---------- welcome / quests ---------- */
.welcome { display: flex; gap: 24px; align-items: center; padding: 28px 30px; margin: 26px 0 18px;
    background: linear-gradient(135deg, rgba(16,19,28,.88), rgba(10,11,16,.88));
    border: 1px solid var(--line2); }
.eyebrow { font-family: var(--head); font-size: 11px; letter-spacing: .32em; color: var(--gold2); margin-bottom: 10px; }
.welcome h2 { font-family: var(--head); font-weight: 900; font-size: clamp(1.4rem, 3vw, 2.2rem);
    line-height: 1.1; letter-spacing: -.01em; margin: 0 0 10px; }
.welcome p { margin: 0; color: rgba(255,255,255,.72); max-width: 640px; }
.quest-title { font-family: var(--head); font-size: 11px; letter-spacing: .28em; color: var(--muted); margin: 6px 0 12px; }

/* ---------- chat rows ---------- */
[data-testid="stChatMessage"] {
    background: transparent !important; padding: 0 !important; margin: 8px 0 20px !important; gap: 0 !important;
}
[data-testid^="stChatMessageAvatar"] { display: none !important; }
[data-testid="stChatMessageContent"] { width: 100%; }

.row-user { display: flex; justify-content: flex-end; margin: 22px 0 8px; }
.bubble-user {
    max-width: 78%; padding: 14px 20px 15px; position: relative; font-size: 19px; line-height: 1.5;
    background: linear-gradient(135deg, rgba(205,165,110,.18), rgba(205,165,110,.05));
    border: 1px solid rgba(239,210,164,.38);
}
.bubble-user::before { content: ""; position: absolute; top: -1px; right: -1px; width: 12px; height: 12px;
    border-top: 2px solid var(--gold); border-right: 2px solid var(--gold); }
.bubble-user .tag { font-family: var(--head); font-size: 10px; letter-spacing: .26em; color: var(--gold2); margin-bottom: 7px; }

.bot-row { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
.bot-row b { font-family: var(--head); letter-spacing: .22em; font-size: 14px; }
.bot-row small { display: block; margin-top: 4px; font-family: var(--body); font-weight: 600; font-size: 12px;
    letter-spacing: .2em; color: var(--muted); }
.badge { margin-left: auto; font-family: var(--head); font-size: 10px; letter-spacing: .22em; padding: 8px 14px;
    border: 1px solid rgba(75,227,164,.5); color: var(--green); background: rgba(75,227,164,.08); }
.badge.err { border-color: rgba(255,111,111,.55); color: #ff8a8a; background: rgba(255,111,111,.08); }

.seed { padding: 11px 16px; margin-bottom: 14px; font-size: 15px; letter-spacing: .04em; color: rgba(255,255,255,.66);
    border: 1px dashed rgba(239,210,164,.28); background: rgba(8,9,13,.6); }
.seed b { font-family: var(--head); font-size: 10px; letter-spacing: .24em; color: var(--gold2); margin-right: 10px; }

/* ---------- generating quest log ---------- */
.quest { padding: 24px 26px; border: 1px solid var(--line2); position: relative;
    background: linear-gradient(135deg, rgba(16,19,28,.92), rgba(9,10,15,.92)); }
.quest-h { font-family: var(--head); font-weight: 900; font-size: clamp(1.3rem, 2.6vw, 1.9rem); margin: 4px 0 4px; }
.quest-sub { color: var(--muted); font-size: 15px; letter-spacing: .06em; margin-bottom: 18px; }
.steps { list-style: none; margin: 0; padding: 0; }
.steps li { display: flex; align-items: center; gap: 14px; padding: 9px 0; border-bottom: 1px solid rgba(255,255,255,.05);
    opacity: 0; animation: stepIn .5s forwards; }
@keyframes stepIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: none; } }
@keyframes vanish { to { opacity: 0; width: 0; margin: 0; } }
@keyframes pop { from { opacity: 0; transform: scale(.4); } to { opacity: 1; transform: scale(1); } }
.st-spin { width: 16px; height: 16px; border-radius: 50%; flex: none; border: 2px solid rgba(239,210,164,.25);
    border-top-color: var(--gold2); animation: spin .8s linear infinite; }
.st-ok { color: var(--green); font-weight: 900; opacity: 0; width: 16px; flex: none; text-align: center;
    animation: pop .25s forwards; }
.steps b { font-family: var(--head); font-size: 11px; letter-spacing: .2em; color: var(--gold2); min-width: 170px; }
.steps em { font-style: normal; color: rgba(255,255,255,.7); font-size: 16px; }
.loadbar { height: 3px; margin-top: 18px; background: rgba(255,255,255,.08); overflow: hidden; }
.loadbar::after { content: ""; display: block; width: 28%; height: 100%;
    background: linear-gradient(90deg, transparent, var(--gold2), transparent); animation: lineMove 1.6s linear infinite; }
@keyframes lineMove { from { transform: translateX(-120%); } to { transform: translateX(460%); } }

/* ---------- document sections ---------- */
.doc-head { display: grid; grid-template-columns: 150px 1fr; gap: 16px; align-items: baseline;
    margin: 44px 0 6px; padding-bottom: 12px; border-bottom: 1px solid var(--line2); }
.doc-no { font-family: var(--head); font-size: 11px; letter-spacing: .22em; color: var(--gold2); }
.doc-title { font-family: var(--head); font-weight: 900; font-size: clamp(1.2rem, 2.4vw, 1.75rem);
    letter-spacing: -.01em; text-transform: uppercase; }

/* ---------- result tabs (unused) ---------- */
[data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
button[data-baseweb="tab"] { background: transparent !important; padding: 12px 18px !important; }
button[data-baseweb="tab"] p { font-family: var(--head) !important; font-size: 11px !important;
    letter-spacing: .2em !important; color: var(--muted) !important; }
button[data-baseweb="tab"][aria-selected="true"] p { color: var(--gold2) !important; }
[data-baseweb="tab-highlight"] { background: var(--gold) !important; height: 2px !important; }
[data-baseweb="tab-border"] { background: transparent !important; }

.tab-pad { height: 10px; }
.media-row { display: grid; grid-template-columns: 340px 1fr; gap: 18px; margin-top: 8px; }
.media-row.reverse { grid-template-columns: 1fr 340px; }
.media-frame { min-height: 260px; overflow: hidden; border: 1px solid var(--line); background: #0e0e0e; }
.media-frame div { width: 100%; height: 100%; min-height: 260px; background-size: cover; background-position: center;
    filter: brightness(.85) saturate(.9); transition: transform .6s ease; }
.media-frame:hover div { transform: scale(1.05); }
.media-copy { padding: 26px 28px; display: flex; flex-direction: column; justify-content: center;
    background: linear-gradient(180deg, rgba(17,16,14,.94), rgba(11,11,10,.94)); border: 1px solid var(--line); }
.label { font-family: var(--head); font-size: 10px; letter-spacing: .26em; color: var(--gold2); margin-bottom: 10px; }
.label.sp { margin-top: 20px; }
.media-title { font-size: 21px; line-height: 1.4; font-weight: 600; }
.media-body { color: rgba(255,255,255,.72); font-size: 17px; line-height: 1.6; }

.g-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 8px; }
.g-grid.two { grid-template-columns: repeat(2, 1fr); }
.g-card { padding: 20px 20px 22px; background: rgba(13,13,12,.92); border: 1px solid var(--line); transition: .25s ease; }
.g-card:hover { transform: translateY(-3px); border-color: rgba(239,210,164,.3); }
.g-no { font-family: var(--head); font-size: 10px; letter-spacing: .2em; color: var(--gold2); margin-bottom: 14px; }
.g-text { color: rgba(255,255,255,.78); font-size: 16px; line-height: 1.6; }

.lvl { position: relative; min-height: 270px; overflow: hidden; border: 1px solid var(--line); background: #0d0d0d; }
.lvl-bg { position: absolute; inset: 0; background-size: cover; background-position: center;
    filter: brightness(.46) saturate(.8); transition: .55s ease; }
.lvl:hover .lvl-bg { transform: scale(1.05); filter: brightness(.58) saturate(.95); }
.lvl::after { content: ""; position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,.05), rgba(0,0,0,.92)); }
.lvl-copy { position: absolute; z-index: 3; left: 20px; right: 20px; bottom: 20px; }
.lvl-name { font-family: var(--head); font-weight: 700; font-size: 17px; margin-bottom: 8px; }
.lvl-desc { color: rgba(255,255,255,.75); font-size: 15px; line-height: 1.5; }
.lvl-desc strong { color: var(--gold2); font-family: var(--head); font-size: 10px; letter-spacing: .2em; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.tags span { font-size: 12px; letter-spacing: .08em; padding: 4px 9px; border: 1px solid rgba(94,231,255,.35);
    color: var(--cyan); background: rgba(94,231,255,.06); }

/* ---------- blueprint (summary + structure diagram) ---------- */
.bp { margin-top: 26px; padding: 26px 26px 30px; border: 1px solid var(--line2);
    background: linear-gradient(180deg, rgba(14,16,24,.94), rgba(8,9,13,.94)); }
.bp-title { font-family: var(--head); font-weight: 900; font-size: clamp(1.2rem, 2.4vw, 1.7rem); margin: 4px 0 6px; }
.bp-sum { color: rgba(255,255,255,.75); font-size: 17px; line-height: 1.6; max-width: 820px; margin-bottom: 20px; }
.score { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 30px; }
.score div { padding: 14px 10px; text-align: center; background: rgba(255,255,255,.03); border: 1px solid var(--line); }
.score b { display: block; font-family: var(--head); font-weight: 900; font-size: 24px; color: var(--gold2); }
.score span { font-family: var(--head); font-size: 9px; letter-spacing: .2em; color: var(--muted); }

.bp-root { width: fit-content; max-width: 100%; margin: 0 auto; padding: 14px 26px; text-align: center;
    border: 1px solid var(--gold); background: rgba(205,165,110,.10); box-shadow: 0 0 26px rgba(205,165,110,.16); }
.bp-root b { font-family: var(--head); font-size: 13px; letter-spacing: .26em; color: var(--gold2); }
.bp-root small { display: block; margin-top: 6px; color: var(--muted); font-size: 14px; }
.bp-drop { width: 1px; height: 26px; background: var(--gold); margin: 0 auto; }
.bp-cols { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; position: relative; padding-top: 26px; }
.bp-cols::before { content: ""; position: absolute; top: 0; left: 12.5%; right: 12.5%; height: 1px; background: var(--gold); }
.bp-col { position: relative; }
.bp-col::before { content: ""; position: absolute; top: -26px; left: 50%; width: 1px; height: 26px; background: var(--gold); }
.bp-node { text-align: center; padding: 12px 8px; font-family: var(--head); font-weight: 700; font-size: 12px;
    letter-spacing: .2em; border: 1px solid; }
.bp-node small { display: block; font-family: var(--body); font-weight: 600; font-size: 11px; letter-spacing: .2em; opacity: .75; margin-bottom: 3px; }
.c1 .bp-node { color: var(--gold2); border-color: rgba(239,210,164,.6); background: rgba(205,165,110,.10); }
.c2 .bp-node { color: var(--cyan); border-color: rgba(94,231,255,.55); background: rgba(94,231,255,.08); }
.c3 .bp-node { color: var(--pink); border-color: rgba(255,111,174,.55); background: rgba(255,111,174,.08); }
.c4 .bp-node { color: var(--green); border-color: rgba(75,227,164,.55); background: rgba(75,227,164,.08); }
.bp-leaves { margin: 10px 0 0 16px; padding-left: 14px; border-left: 1px solid var(--line2); display: grid; gap: 7px; }
.bp-leaf { position: relative; padding: 9px 11px; font-size: 14px; line-height: 1.35; background: rgba(255,255,255,.03);
    border: 1px solid var(--line); color: rgba(255,255,255,.82); }
.bp-leaf::before { content: ""; position: absolute; left: -15px; top: 50%; width: 14px; height: 1px; background: var(--line2); }
.bp-leaf span { display: block; font-family: var(--head); font-size: 9px; letter-spacing: .18em; color: var(--muted); margin-bottom: 3px; }
.bp-leaf em { font-style: normal; }
.bp-next { margin-top: 24px; color: var(--muted); font-size: 15px; letter-spacing: .04em; }

/* ---------- native containers ---------- */
details { background: rgba(11,11,11,.9) !important; border: 1px solid var(--line) !important; border-radius: 0 !important;
    margin-bottom: 7px !important; }
[data-testid="stExpander"] summary p { font-family: var(--head) !important; font-size: 11px !important; letter-spacing: .14em; }
.err-box { padding: 22px 24px; border: 1px solid rgba(255,111,111,.4); background: rgba(40,12,14,.55); margin-bottom: 10px; }

/* ---------- chat input ---------- */
[data-testid="stBottom"] > div { background: linear-gradient(180deg, rgba(5,6,10,0), #05060a 42%) !important; }
[data-testid="stBottomBlockContainer"] { max-width: 1080px !important; padding-bottom: 22px !important; }
[data-testid="stChatInput"] {
    background: #0b0d13 !important;
    border: 1px solid rgba(239,210,164,.5) !important;
    border-radius: 0 !important;
    box-shadow: 0 0 0 1px rgba(94,231,255,.08), 0 0 30px rgba(205,165,110,.14);
}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] div[data-baseweb="textarea"],
[data-testid="stChatInput"] div[data-baseweb="base-input"] {
    background: transparent !important; border-radius: 0 !important; border: 0 !important;
}
[data-testid="stChatInput"] textarea {
    color: #f7f2ea !important; font-family: var(--body) !important; font-size: 18px !important; caret-color: var(--cyan);
}
[data-testid="stChatInput"] textarea::placeholder { color: rgba(255,255,255,.4) !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--gold) !important; color: #0a0a0a !important; border-radius: 0 !important; }

/* ---------- responsive ---------- */
@media (max-width: 950px) {
    .media-row, .media-row.reverse, .g-grid, .g-grid.two, .bp-cols { grid-template-columns: 1fr; }
    .bp-cols::before, .bp-col::before, .bp-drop { display: none; }
    .bp-cols { padding-top: 16px; }
    .score { grid-template-columns: repeat(3, 1fr); }
    .doc-head { grid-template-columns: 1fr; gap: 6px; }
    .welcome { flex-direction: column; align-items: flex-start; }
    .bubble-user { max-width: 94%; }
    .hud-xp { display: none; }
    .steps b { min-width: 120px; }
}
</style>
"""


# ============================================================
# SESSION STATE
# ============================================================

QUESTS = [
    (
        "☠ SPACE STATION HORROR",
        "A survival horror game on an abandoned space station where the "
        "station AI is hiding what happened.",
    ),
    (
        "🕌 OLD JEDDAH MYSTERY",
        "A story-driven mystery set in the historic Al-Balad district of "
        "Jeddah, where the player follows clues left by old Red Sea traders.",
    ),
    (
        "🌊 RED SEA DIVER",
        "An underwater exploration adventure in the Red Sea where the player "
        "restores coral reefs and uncovers a sunken ancient port.",
    ),
    (
        "🤖 CO-OP ROBOT PLATFORMER",
        "A cooperative 3D platformer where two small robots repair a broken "
        "floating city together.",
    ),
]

PIPELINE_STEPS = [
    ("SEED", "Reading your world seed"),
    ("STORY ENGINE", "Premise, conflict and characters"),
    ("WORLD ENGINE", "Levels, settings and progression"),
    ("GAMEPLAY ENGINE", "Core loop and key mechanics"),
    ("CLAIM ROUTER", "Extracting factual and cultural claims"),
    ("VERIFICATION", "Checking claims against sources"),
    ("REVISION GATE", "Fixing weak spots and assembling the GDD"),
]

if "messages" not in st.session_state:
    # Each item: {"role": "user", "text": str}
    #         or {"role": "assistant", "kind": "result" | "error", ...}
    st.session_state.messages = []

if "pending_idea" not in st.session_state:
    st.session_state.pending_idea = None

if "generation_mode" not in st.session_state:
    # FAST is the default demo mode.
    st.session_state.generation_mode = "FAST"

if "max_rounds" not in st.session_state:
    st.session_state.max_rounds = 1

if "scroll_pending" not in st.session_state:
    st.session_state.scroll_pending = False


page = st.query_params.get("page", "intro")

if isinstance(page, list):
    page = page[0]

# Old pages (home / create / generating / project ...) now live inside the chat.
if page not in {"intro", "chat"}:
    page = "chat" if page in {
        "transition", "home", "create", "generating", "reveal", "project",
    } else "intro"


render_html(BASE_CSS)


# ============================================================
# INTRO  ·  3D mascot whose head follows the cursor
# ============================================================

if page == "intro":

    render_html(INTRO_CSS)

    embed_html(INTRO_3D_HTML, height=760)

    if st.button("▶  PRESS START", key="start_btn"):
        go("chat")

    st.stop()


# ============================================================
# CHAT PAGE  ·  assets + style
# ============================================================

HERO = asset_uri("hero.jpg")
STORY = asset_uri("story.jpg")
WORLD = asset_uri("world.jpg")
GAMEPLAY = asset_uri("gameplay.jpg")

# Every image is embedded ONCE as a CSS class (not repeated per card).
IMG_CSS = (
    "<style>"
    f".stApp::before{{background-image:url('{WORLD}');}}"
    f".img-story{{background-image:url('{STORY}');}}"
    f".img-gameplay{{background-image:url('{GAMEPLAY}');}}"
    f".img-lvl0{{background-image:url('{WORLD}');}}"
    f".img-lvl1{{background-image:url('{HERO}');}}"
    f".img-lvl2{{background-image:url('{GAMEPLAY}');}}"
    f".img-lvl3{{background-image:url('{STORY}');}}"
    "</style>"
)

render_html(CHAT_CSS)
render_html(IMG_CSS)


# ============================================================
# RESULT HELPERS
# ============================================================

def extract_result(result):
    game_state = result["game_state"]

    story = game_state.story
    gameplay = game_state.gameplay
    levels = game_state.levels

    scoped_claims = result.get("scoped_claims")
    evidence_packs = result.get("evidence_packs")
    verification = result.get("verification_results")

    claims = (
        as_list(getattr(scoped_claims, "atomic_claims", []))
        if scoped_claims else []
    )
    verification_items = (
        as_list(getattr(verification, "verifications", []))
        if verification else []
    )
    claim_packs = (
        as_list(getattr(evidence_packs, "claim_packs", []))
        if evidence_packs else []
    )

    supported = sum(
        1
        for item in verification_items
        if str(getattr(item, "verdict", "")).upper() == "SUPPORTED"
    )

    source_urls = set()
    for pack in claim_packs:
        for evidence in as_list(getattr(pack, "evidence", [])):
            url = getattr(evidence, "source_url", None)
            if url:
                source_urls.add(url)

    return {
        "premise": attr(story, "premise"),
        "conflict": attr(story, "central_conflict"),
        "characters": as_list(attr(story, "characters", [])),
        "loop": attr(gameplay, "core_gameplay_loop"),
        "progression": attr(gameplay, "progression_system"),
        "mechanics": as_list(attr(gameplay, "key_mechanics", [])),
        "level_names": as_list(attr(levels, "level_names", [])),
        "level_settings": as_list(attr(levels, "level_settings", [])),
        "key_challenges": as_list(attr(levels, "key_challenges", [])),
        "mechanic_focus": as_list(attr(levels, "mechanic_focus", [])),
        "progression_purpose": as_list(attr(levels, "progression_purpose", [])),
        "claims": claims,
        "verification_items": verification_items,
        "claim_packs": claim_packs,
        "supported": supported,
        "sources": len(source_urls),
        "revisions": result.get("revision_round", 0),
        "status": result.get("final_status", "UNKNOWN"),
        "trace": as_list(result.get("execution_trace", [])),
        "revision_decisions": result.get("revision_decisions"),
    }


def nth(items, index):
    return items[index] if index < len(items) else ""


# ---------- tab content ----------

def story_html(d):
    return f"""
    <div class="tab-pad"></div>
    <div class="media-row">
        <div class="media-frame"><div class="img-story"></div></div>
        <div class="media-copy">
            <div class="label">PREMISE</div>
            <div class="media-title">{esc(d['premise'])}</div>
            <div class="label sp">CENTRAL CONFLICT</div>
            <div class="media-body">{esc(d['conflict'])}</div>
        </div>
    </div>
    """


def characters_html(d):
    cards = "".join(
        f"""
        <article class="g-card">
            <div class="g-no">CHARACTER {i:02d}</div>
            <div class="g-text">{esc(c)}</div>
        </article>
        """
        for i, c in enumerate(d["characters"], start=1)
    )
    return f'<div class="tab-pad"></div><div class="g-grid">{cards}</div>'


def gameplay_html(d):
    mechanics = "".join(
        f"""
        <article class="g-card">
            <div class="g-no">SYSTEM {i:02d}</div>
            <div class="g-text">{esc(m)}</div>
        </article>
        """
        for i, m in enumerate(d["mechanics"], start=1)
    )
    return f"""
    <div class="tab-pad"></div>
    <div class="media-row reverse">
        <div class="media-copy">
            <div class="label">CORE LOOP</div>
            <div class="media-title">{esc(d['loop'])}</div>
            <div class="label sp">PROGRESSION</div>
            <div class="media-body">{esc(d['progression'])}</div>
        </div>
        <div class="media-frame"><div class="img-gameplay"></div></div>
    </div>
    <div class="g-grid two" style="margin-top:12px">{mechanics}</div>
    """


def levels_html(d):
    cards = ""

    for i, name in enumerate(d["level_names"]):
        setting = nth(d["level_settings"], i)
        challenge = nth(d["key_challenges"], i)
        focus = nth(d["mechanic_focus"], i)
        purpose = nth(d["progression_purpose"], i)

        tags = ""
        if focus:
            tags += f"<span>FOCUS · {esc(clip(focus, 48))}</span>"
        if purpose:
            tags += f"<span>PURPOSE · {esc(clip(purpose, 56))}</span>"

        cards += f"""
        <article class="lvl">
            <div class="lvl-bg img-lvl{i % 4}"></div>
            <div class="lvl-copy">
                <div class="g-no">LEVEL {i + 1:02d}</div>
                <div class="lvl-name">{esc(name)}</div>
                <div class="lvl-desc">
                    {esc(setting)}
                    <br><br>
                    <strong>KEY CHALLENGE</strong><br>
                    {esc(challenge)}
                </div>
                <div class="tags">{tags}</div>
            </div>
        </article>
        """

    return f'<div class="tab-pad"></div><div class="g-grid two">{cards}</div>'


def render_evidence(d):
    st.write("")

    if not (d["claims"] or d["claim_packs"] or d["verification_items"]):
        st.caption("No factual claims were routed for this world.")

    for index, claim in enumerate(d["claims"], start=1):
        with st.expander(
            f"CLAIM {index:02d} / {getattr(claim, 'scope', 'UNCLASSIFIED')}"
        ):
            st.write(getattr(claim, "claim", ""))
            rationale = getattr(claim, "rationale", "")
            if rationale:
                st.caption(rationale)

    if d["claim_packs"]:
        st.markdown("### Cultural Evidence")

        for pack_index, pack in enumerate(d["claim_packs"], start=1):
            with st.expander(f"EVIDENCE PACK {pack_index:02d}"):
                st.write(getattr(pack, "claim", ""))

                for evidence in as_list(getattr(pack, "evidence", [])):
                    st.markdown(f"**{getattr(evidence, 'source_name', 'Source')}**")
                    st.write(getattr(evidence, "text", ""))

                    url = getattr(evidence, "source_url", None)
                    if url:
                        st.markdown(f"[OPEN OFFICIAL SOURCE ↗]({url})")

    if d["verification_items"]:
        st.markdown("### Verification")

        for index, item in enumerate(d["verification_items"], start=1):
            with st.expander(
                f"VERIFICATION {index:02d} / {getattr(item, 'verdict', '')}"
            ):
                st.write(getattr(item, "claim", ""))
                st.markdown("**Reason**")
                st.write(getattr(item, "reason", ""))

    with st.expander("SYSTEM TRACE / TECHNICAL VIEW"):
        for index, stage in enumerate(d["trace"], start=1):
            st.markdown(f"**{index:02d} — {str(stage).replace('_', ' ').title()}**")

        decisions = as_list(getattr(d["revision_decisions"], "decisions", []))

        if decisions:
            st.divider()
            st.markdown("### Revision Gate")

            for decision in decisions:
                st.markdown(f"**{getattr(decision, 'action', '')}**")
                st.write(getattr(decision, "claim", ""))


# ---------- blueprint: summary + GDD structure diagram ----------

def blueprint_html(d, idea):
    n_char = len(d["characters"])
    n_mech = len(d["mechanics"])
    n_lvl = len(d["level_names"])
    n_claims = len(d["claims"])
    n_ver = len(d["verification_items"])

    summary = (
        f"This design document contains {n_char} characters, {n_mech} core "
        f"mechanics and {n_lvl} levels"
    )
    if n_ver:
        summary += (
            f", with {d['supported']} of {n_ver} verified claims supported "
            f"by {d['sources']} source(s)"
        )
    summary += "."

    def leaf(label, value):
        return (
            f'<div class="bp-leaf"><span>{esc(label)}</span>'
            f"<em>{esc(value)}</em></div>"
        )

    story_leaves = (
        leaf("PREMISE", clip(d["premise"], 62))
        + leaf("CENTRAL CONFLICT", clip(d["conflict"], 62))
        + leaf("CHARACTERS", f"× {n_char}")
    )
    gameplay_leaves = (
        leaf("CORE LOOP", clip(d["loop"], 62))
        + leaf("PROGRESSION", clip(d["progression"], 62))
        + leaf("MECHANICS", f"× {n_mech}")
    )

    shown = d["level_names"][:6]
    level_leaves = "".join(
        leaf(f"LEVEL {i:02d}", clip(name, 34))
        for i, name in enumerate(shown, start=1)
    )
    if n_lvl > len(shown):
        level_leaves += leaf("MORE", f"+ {n_lvl - len(shown)} levels")

    verify_leaves = (
        leaf("CLAIMS", n_claims)
        + leaf("SUPPORTED", f"{d['supported']} / {n_ver}")
        + leaf("SOURCES", d["sources"])
        + leaf("REVISION ROUNDS", d["revisions"])
    )

    columns = [
        ("c1", "01", "STORY", story_leaves),
        ("c2", "02", "GAMEPLAY", gameplay_leaves),
        ("c3", "03", "LEVELS", level_leaves),
        ("c4", "04", "VERIFICATION", verify_leaves),
    ]
    cols_html = "".join(
        f"""
        <div class="bp-col {cls}">
            <div class="bp-node"><small>{no}</small>{title}</div>
            <div class="bp-leaves">{leaves}</div>
        </div>
        """
        for cls, no, title, leaves in columns
    )

    tiles = [
        (n_char, "CHARACTERS"),
        (n_mech, "MECHANICS"),
        (n_lvl, "LEVELS"),
        (n_claims, "CLAIMS"),
        (f"{d['supported']}/{n_ver}", "VERIFIED"),
        (d["sources"], "SOURCES"),
    ]
    tiles_html = "".join(f"<div><b>{esc(v)}</b><span>{esc(k)}</span></div>" for v, k in tiles)

    return f"""
    <section class="bp box">
        <div class="eyebrow">FINAL REPORT</div>
        <div class="bp-title">GDD BLUEPRINT</div>
        <div class="bp-sum">{esc(summary)}</div>
        <div class="score">{tiles_html}</div>

        <div class="bp-root">
            <b>GAME DESIGN DOCUMENT</b>
            <small>{esc(clip(idea, 90))}</small>
        </div>
        <div class="bp-drop"></div>
        <div class="bp-cols">{cols_html}</div>

        <div class="bp-next">▶ Type a new idea below to forge another world.</div>
    </section>
    """


def build_markdown(d, idea):
    lines = [
        "# Game Design Document",
        "",
        f"> World seed: {idea}",
        "",
        "## Story",
        "",
        f"**Premise:** {d['premise']}",
        "",
        f"**Central conflict:** {d['conflict']}",
        "",
        "## Characters",
        "",
    ]
    lines += [f"{i}. {c}" for i, c in enumerate(d["characters"], start=1)]
    lines += [
        "",
        "## Gameplay",
        "",
        f"**Core loop:** {d['loop']}",
        "",
        f"**Progression:** {d['progression']}",
        "",
        "### Key mechanics",
        "",
    ]
    lines += [f"- {m}" for m in d["mechanics"]]
    lines += ["", "## Levels", ""]

    for i, name in enumerate(d["level_names"]):
        lines.append(f"### {i + 1}. {name}")
        lines.append("")
        lines.append(f"- Setting: {nth(d['level_settings'], i)}")
        lines.append(f"- Key challenge: {nth(d['key_challenges'], i)}")
        focus = nth(d["mechanic_focus"], i)
        purpose = nth(d["progression_purpose"], i)
        if focus:
            lines.append(f"- Mechanic focus: {focus}")
        if purpose:
            lines.append(f"- Progression purpose: {purpose}")
        lines.append("")

    lines += [
        "## Verification",
        "",
        f"- Claims: {len(d['claims'])}",
        f"- Supported: {d['supported']} / {len(d['verification_items'])}",
        f"- Sources: {d['sources']}",
        f"- Revision rounds: {d['revisions']}",
        "",
    ]
    return "\n".join(lines)


# ============================================================
# MESSAGE RENDERERS
# ============================================================

def bot_header(title, subtitle, badge="", badge_class=""):
    badge_html = (
        f'<span class="badge {badge_class}">{esc(badge)}</span>' if badge else ""
    )
    return f"""
    <div class="bot-row">
        <span class="bot-face"><i></i><i></i></span>
        <div><b>{esc(title)}</b><small>{esc(subtitle)}</small></div>
        {badge_html}
    </div>
    """


def render_user(text):
    render_html(f"""
    <div class="row-user">
        <div class="bubble-user">
            <div class="tag">PLAYER 01 · WORLD SEED</div>
            {esc_br(text)}
        </div>
    </div>
    """)


def stream_words(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.028)


def doc_head(no, title):
    return f"""
    <div class="doc-head">
        <div class="doc-no">{no}</div>
        <div class="doc-title">{esc(title)}</div>
    </div>
    """


def render_result(msg, index):
    d = extract_result(msg["result"])

    with st.chat_message("assistant"):

        render_html(bot_header(
            "HIVE",
            f"WORLD ENGINE · {msg.get('mode', 'FAST')}",
            "MISSION COMPLETE",
        ))

        intro = (
            f"Mission complete. I forged a world with "
            f"**{len(d['characters'])} characters**, "
            f"**{len(d['mechanics'])} core mechanics** and "
            f"**{len(d['level_names'])} levels**. "
            f"Here is your full design document, top to bottom."
        )

        if msg.get("streamed"):
            st.markdown(intro)
        else:
            st.write_stream(stream_words(intro))
            msg["streamed"] = True

        render_html(doc_head("01 / STORY", "Narrative foundation"))
        render_html(story_html(d))

        render_html(doc_head("02 / CHARACTERS", "The people inside the world"))
        render_html(characters_html(d))

        render_html(doc_head("03 / GAMEPLAY", "How the world becomes playable"))
        render_html(gameplay_html(d))

        render_html(doc_head("04 / LEVELS", "Level progression"))
        render_html(levels_html(d))

        render_html(doc_head("05 / EVIDENCE", "Verification behind the world"))
        render_evidence(d)

        render_html(blueprint_html(d, msg["idea"]))

        st.download_button(
            "⬇ EXPORT GDD (.MD)",
            data=build_markdown(d, msg["idea"]),
            file_name="gamehive_gdd.md",
            mime="text/markdown",
            key=f"download_{index}",
        )


def render_error(msg, index, is_last):
    with st.chat_message("assistant"):
        render_html(bot_header(
            "HIVE",
            "WORLD ENGINE · ERROR",
            "GENERATION FAILED",
            "err",
        ))
        render_html(f"""
        <div class="err-box">
            GameHive hit an error while generating this world.
            Your idea is saved, so you can retry it right away.
        </div>
        """)

        with st.expander("TECHNICAL DETAILS"):
            st.code(msg.get("trace") or msg.get("error", ""), language="text")

        if is_last and st.button("↻ RETRY THIS WORLD", key=f"retry_{index}"):
            queue_idea(msg["idea"])


def generating_html(idea, mode):
    items = ""
    last = len(PIPELINE_STEPS) - 1

    for i, (tag, text) in enumerate(PIPELINE_STEPS):
        start = i * 4

        if i < last:
            spinner = (
                f'<span class="st-spin" style="animation:spin .8s linear infinite,'
                f'vanish .01s forwards;animation-delay:0s,{start + 4}s"></span>'
            )
            ok = f'<span class="st-ok" style="animation-delay:{start + 4}s">✓</span>'
        else:
            spinner = '<span class="st-spin"></span>'
            ok = ""

        items += (
            f'<li style="animation-delay:{start}s">{spinner}{ok}'
            f"<b>{esc(tag)}</b><em>{esc(text)}</em></li>"
        )

    return f"""
    <div class="quest box">
        {bot_header("HIVE", f"WORLD ENGINE · {mode}", "IN PROGRESS")}
        <div class="quest-h">Forging your world…</div>
        <div class="quest-sub">Autonomous design pipeline active. Larger worlds can take a minute.</div>
        <ul class="steps">{items}</ul>
        <div class="loadbar"></div>
    </div>
    """


def scroll_to_anchor():
    embed_html(
        f"""
        <script>
        /* {time.time()} */
        (function () {{
            var tries = 0;
            function run() {{
                try {{
                    var a = window.parent.document.getElementById('gh-anchor');
                    if (a) {{ a.scrollIntoView({{ behavior: 'smooth', block: 'start' }}); return; }}
                }} catch (e) {{}}
                if (++tries < 14) setTimeout(run, 150);
            }}
            run();
        }})();
        </script>
        """,
        height=1,
    )


# ============================================================
# ACTIONS
# ============================================================

def queue_idea(text):
    text = (text or "").strip()

    if not text:
        return

    st.session_state.messages.append({"role": "user", "text": text})
    st.session_state.pending_idea = text
    st.session_state.max_rounds = (
        1 if st.session_state.generation_mode == "FAST" else 2
    )
    st.session_state.scroll_pending = True
    st.rerun()


def reset_session():
    st.session_state.messages = []
    st.session_state.pending_idea = None
    st.session_state.scroll_pending = False
    st.rerun()


# ============================================================
# CHAT PAGE
# ============================================================

pending = st.session_state.pending_idea
messages = st.session_state.messages

# The input is declared first so it stays visible (disabled) while generating.
prompt = st.chat_input(
    "Describe your game idea…  (Enter to launch)",
    disabled=bool(pending),
)

if prompt:
    queue_idea(prompt)


# ---------- HUD ----------

worlds = sum(1 for m in messages if m.get("kind") == "result")
xp = min(100, 30 + worlds * 14)

render_html(f"""
<header class="hud">
    <div class="hud-brand">
        <span class="bot-face"><i></i><i></i></span>
        <div>GAMEHIVE<small>QUEST BOARD</small></div>
    </div>
    <div class="hud-right">
        <div class="hud-chip"><i></i>SYSTEM ONLINE</div>
        <div class="hud-xp">
            <span>LV {1 + worlds:02d}</span>
            <div class="xp"><b style="width:{xp}%"></b></div>
            <span>{worlds} WORLD{'S' if worlds != 1 else ''}</span>
        </div>
    </div>
</header>
<div style="height:14px"></div>
""")

col_mode, col_new, col_intro = st.columns([3.2, 1, 1])

with col_mode:
    st.radio(
        "Generation mode",
        options=["FAST", "DEEP VERIFICATION"],
        key="generation_mode",
        horizontal=True,
        label_visibility="collapsed",
        help=(
            "FAST uses up to 1 automatic revision round. "
            "DEEP VERIFICATION uses up to 2 rounds."
        ),
    )

with col_new:
    if st.button("↺ NEW SESSION", use_container_width=True):
        reset_session()

with col_intro:
    if st.button("← INTRO", use_container_width=True):
        go("intro")


# ---------- welcome + quests ----------

if not messages and not pending:

    render_html("""
    <section class="welcome box">
        <span class="bot-face big"><i></i><i></i></span>
        <div>
            <div class="eyebrow">MISSION BRIEFING</div>
            <h2>What do you want to build, player?</h2>
            <p>Describe any game idea. I will forge a complete design document:
               story, characters, gameplay and levels, while cultural facts
               are verified in the background.</p>
        </div>
    </section>
    <div class="quest-title">▶ OR PICK A QUEST</div>
    """)

    quest_cols = st.columns(2)

    for i, (label, quest_prompt) in enumerate(QUESTS):
        with quest_cols[i % 2]:
            if st.button(
                label,
                key=f"quest_{i}",
                help=quest_prompt,
                use_container_width=True,
            ):
                queue_idea(quest_prompt)


# ---------- conversation ----------

anchor_index = len(messages) - 1

for i, msg in enumerate(messages):

    if i == anchor_index:
        render_html('<div id="gh-anchor" style="scroll-margin-top:12px"></div>')

    if msg["role"] == "user":
        render_user(msg["text"])

    elif msg.get("kind") == "result":
        render_result(msg, i)

    elif msg.get("kind") == "error":
        render_error(msg, i, is_last=(i == anchor_index) and not pending)

if st.session_state.scroll_pending:
    st.session_state.scroll_pending = False
    scroll_to_anchor()


# ---------- generation (blocking call to the existing LangGraph backend) ----------

if pending:

    mode = st.session_state.generation_mode

    with st.chat_message("assistant"):
        render_html(generating_html(pending, mode))

        try:
            print("\n=================================")
            print("GAMEHIVE USER WORLD SEED")
            print("=================================")
            print(repr(pending))
            print("Mode:", mode)
            print("Max revision rounds:", st.session_state.max_rounds)

            started = time.perf_counter()

            result = run_gamehive_graph(
                # The exact user prompt is forwarded to the existing backend.
                game_idea=pending,
                max_revision_rounds=st.session_state.max_rounds,
            )

            st.session_state.messages.append({
                "role": "assistant",
                "kind": "result",
                "idea": pending,
                "result": result,
                "seconds": time.perf_counter() - started,
                "mode": mode,
                "streamed": False,
            })

        except Exception as error:
            st.session_state.messages.append({
                "role": "assistant",
                "kind": "error",
                "idea": pending,
                "error": str(error),
                "trace": traceback.format_exc(),
            })

    st.session_state.pending_idea = None
    st.session_state.scroll_pending = True
    st.rerun()
