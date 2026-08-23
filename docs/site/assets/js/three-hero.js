/* UPF-Insight 3D hero — silicon die with glowing power domains.
   Three.js r160 via CDN (ES module). Lazy: only runs when canvas
   is on screen. Honors prefers-reduced-motion. */

import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js";

const canvas = document.getElementById("hero-canvas");
if (canvas) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(4.6, 3.6, 5.4);

  const renderer = new THREE.WebGLRenderer({
    canvas, antialias: true, alpha: true,
  });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.enablePan = false;
  controls.minDistance = 4;
  controls.maxDistance = 12;
  controls.autoRotate = !reduced;
  controls.autoRotateSpeed = 0.9;

  scene.add(new THREE.AmbientLight(0xbfd4ff, 0.7));
  const key = new THREE.DirectionalLight(0x22d3ee, 2.2);
  key.position.set(4, 6, 3);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x818cf8, 1.4);
  rim.position.set(-5, -2, -4);
  scene.add(rim);

  /* ── the die ─────────────────────────────────────────────── */
  const die = new THREE.Group();

  // substrate
  const substrate = new THREE.Mesh(
    new THREE.BoxGeometry(4.4, 0.28, 4.4),
    new THREE.MeshStandardMaterial({
      color: 0x101627, metalness: 0.85, roughness: 0.32,
    })
  );
  die.add(substrate);

  // top face — dark silicon
  const top = new THREE.Mesh(
    new THREE.BoxGeometry(4.15, 0.16, 4.15),
    new THREE.MeshStandardMaterial({
      color: 0x0a0e18, metalness: 0.9, roughness: 0.25,
    })
  );
  top.position.y = 0.22;
  die.add(top);

  /* power domains — emissive blocks on a 4×4 grid with a few "off" */
  const domainColors = [0x22d3ee, 0x818cf8, 0xc084fc, 0x34d399];
  const offMat = new THREE.MeshStandardMaterial({
    color: 0x141a2c, metalness: 0.7, roughness: 0.5,
  });

  const rng = mulberry32(20240801); // deterministic layout
  const domains = [];
  const N = 4;
  for (let gx = 0; gx < N; gx++) {
    for (let gz = 0; gz < N; gz++) {
      if (rng() < 0.18) continue; // some cells empty
      const powered = rng() > 0.22;
      const w = 0.62 + rng() * 0.22;
      const d = 0.62 + rng() * 0.22;
      const h = 0.16 + rng() * 0.34;
      const mat = powered
        ? new THREE.MeshStandardMaterial({
            color: 0x0d1322,
            emissive: domainColors[(gx * N + gz) % domainColors.length],
            emissiveIntensity: 0.55 + rng() * 0.75,
            metalness: 0.4,
            roughness: 0.35,
          })
        : offMat;
      const block = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
      block.position.set(
        (gx - (N - 1) / 2) * 1.02 + (rng() - 0.5) * 0.12,
        0.38 + h / 2,
        (gz - (N - 1) / 2) * 1.02 + (rng() - 0.5) * 0.12
      );
      die.add(block);
      if (powered) domains.push({ mesh: block, base: mat.emissiveIntensity, phase: rng() * Math.PI * 2 });
    }
  }

  // edge glow frame
  const frame = new THREE.Mesh(
    new THREE.BoxGeometry(4.55, 0.1, 4.55),
    new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.14 })
  );
  frame.position.y = 0.02;
  die.add(frame);

  // under-glow plane
  const glow = new THREE.Mesh(
    new THREE.PlaneGeometry(9, 9),
    new THREE.MeshBasicMaterial({
      map: makeGlowTexture(), transparent: true, opacity: 0.5, depthWrite: false,
    })
  );
  glow.rotation.x = -Math.PI / 2;
  glow.position.y = -0.45;
  die.add(glow);

  scene.add(die);

  /* floating rule-code particles */
  const particleCount = 90;
  const positions = new Float32Array(particleCount * 3);
  const prng = mulberry32(77);
  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (prng() - 0.5) * 10;
    positions[i * 3 + 1] = (prng() - 0.5) * 7;
    positions[i * 3 + 2] = (prng() - 0.5) * 10;
  }
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const particles = new THREE.Points(
    pGeo,
    new THREE.PointsMaterial({
      color: 0x22d3ee, size: 0.045, transparent: true,
      opacity: 0.65, sizeAttenuation: true,
    })
  );
  scene.add(particles);

  function makeGlowTexture() {
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(128, 128, 10, 128, 128, 128);
    grad.addColorStop(0, "rgba(34,211,238,0.55)");
    grad.addColorStop(0.5, "rgba(129,140,248,0.18)");
    grad.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 256, 256);
    return new THREE.CanvasTexture(c);
  }

  function mulberry32(a) {
    return () => {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* resize to element box */
  function resize() {
    const { clientWidth: w, clientHeight: h } = canvas.parentElement;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }
  resize();
  new ResizeObserver(resize).observe(canvas.parentElement);

  /* render loop — pauses when tab hidden or canvas off-screen */
  let visible = true;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; },
    { threshold: 0.05 }).observe(canvas);

  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    if (!visible || document.hidden) return;
    const t = clock.getElapsedTime();
    // breathing emissive pulse per domain
    for (const d of domains) {
      d.mesh.material.emissiveIntensity =
        d.base * (0.72 + 0.28 * Math.sin(t * 1.4 + d.phase));
    }
    particles.rotation.y = t * 0.03;
    glow.material.opacity = 0.42 + 0.12 * Math.sin(t * 0.9);
    controls.update();
    renderer.render(scene, camera);
  });
}
