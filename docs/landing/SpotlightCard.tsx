import React, { useRef, useState, useCallback } from "react";

/* ═══════════════════════════════════════════════════════════════════════════
 * SpotlightCard — Clerk-style mouse-following glow
 *
 * How it works:
 *   1. onMouseMove calculates X/Y relative to the card (not viewport)
 *   2. Coordinates stored as CSS custom properties --mouse-x / --mouse-y
 *   3. A hidden ::after-style div uses a radial-gradient positioned at those vars
 *   4. A mask-image clips the gradient to a soft circle around the cursor
 *   5. Hover state toggles opacity for smooth fade in/out
 *
 * No Framer Motion. No external libs. Native React + Tailwind + CSS vars.
 * ═══════════════════════════════════════════════════════════════════════════ */

interface SpotlightCardProps {
  children: React.ReactNode;
  className?: string;
  /** Glow color — defaults to blue accent */
  glowColor?: string;
  /** Glow opacity at cursor center (0-1) */
  glowOpacity?: number;
  /** Radius of the visible glow circle in px */
  glowRadius?: number;
  /** Dot grid: dot radius in px (0 = no dots, just soft glow) */
  dotSize?: number;
  /** Dot grid: spacing between dots in px */
  dotSpacing?: number;
}

export function SpotlightCard({
  children,
  className = "",
  glowColor = "91, 155, 245", // #5b9bf5
  glowOpacity = 0.7,
  glowRadius = 280,
  dotSize = 1.5,
  dotSpacing = 12,
}: SpotlightCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  }, []);

  const handleMouseEnter = useCallback(() => setIsHovered(true), []);
  const handleMouseLeave = useCallback(() => setIsHovered(false), []);

  /* ── Build the glow background ── */
  // Dot grid: repeating radial-gradient that creates a grid of small dots
  // Mask: radial-gradient that only reveals dots near the cursor
  const glowStyle: React.CSSProperties = {
    opacity: isHovered ? 1 : 0,
    transition: "opacity 300ms ease",
    backgroundImage:
      dotSize > 0
        ? `radial-gradient(circle, rgba(${glowColor}, ${glowOpacity}) ${dotSize}px, transparent ${dotSize}px)`
        : `radial-gradient(circle 120px, rgba(${glowColor}, ${glowOpacity}), transparent)`,
    backgroundSize: dotSize > 0 ? `${dotSpacing}px ${dotSpacing}px` : undefined,
    maskImage: `radial-gradient(circle ${glowRadius}px at ${mousePos.x}px ${mousePos.y}px, black 0%, transparent 100%)`,
    WebkitMaskImage: `radial-gradient(circle ${glowRadius}px at ${mousePos.x}px ${mousePos.y}px, black 0%, transparent 100%)`,
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative overflow-hidden rounded-xl border border-white/[0.06] bg-[#0c0c12] ${className}`}
      style={{ "--mouse-x": `${mousePos.x}px`, "--mouse-y": `${mousePos.y}px` } as React.CSSProperties}
    >
      {/* Spotlight glow layer */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={glowStyle}
      />

      {/* Border glow — subtle highlight on the card edge nearest cursor */}
      <div
        className="pointer-events-none absolute inset-0 z-0 rounded-xl transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(circle ${glowRadius * 0.6}px at ${mousePos.x}px ${mousePos.y}px, rgba(${glowColor}, 0.15), transparent 70%)`,
          WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          WebkitMaskComposite: "xor",
          maskComposite: "exclude",
          padding: "1px",
        }}
      />

      {/* Card content */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Demo — 3 feature cards in a grid
 *
 * Usage in your app:
 *
 *   import { SpotlightCard } from "./SpotlightCard";
 *
 *   <div className="grid grid-cols-3 gap-4">
 *     <SpotlightCard>
 *       <div className="p-6">...</div>
 *     </SpotlightCard>
 *   </div>
 *
 * Color variants:
 *
 *   <SpotlightCard glowColor="52, 211, 153">   ← green (adversarial)
 *   <SpotlightCard glowColor="245, 158, 11">    ← amber (warning)
 *   <SpotlightCard glowColor="239, 68, 68">     ← red (error)
 *
 * Soft glow (no dot grid):
 *
 *   <SpotlightCard dotSize={0} glowOpacity={0.15}>
 * ═══════════════════════════════════════════════════════════════════════════ */

export default function SpotlightCardDemo() {
  const features = [
    {
      title: "74 Semantic Rules",
      description: "Deterministic UPF validation across 6 layers and 11 categories. Every finding traces to a source line.",
      tag: "VALIDATION",
      glow: "91, 155, 245", // blue
    },
    {
      title: "42/42 Mutations Detected",
      description: "Adversarial corpus with intentional defects across supply, switch, isolation, retention, and PST categories.",
      tag: "ADVERSARIAL",
      glow: "52, 211, 153", // green
    },
    {
      title: "Zero LLM Calls",
      description: "No probabilistic output. No cloud dependency. Pure deterministic analysis — same input, same output, always.",
      tag: "ARCHITECTURE",
      glow: "245, 158, 11", // amber
    },
  ];

  return (
    <div className="min-h-screen bg-[#08080c] p-8">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-2 text-3xl font-bold text-white">Features</h1>
        <p className="mb-8 text-sm text-gray-500">
          Hover over any card to see the spotlight glow effect.
        </p>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {features.map((f) => (
            <SpotlightCard key={f.title} glowColor={f.glow}>
              <div className="p-6">
                <div className="mb-3 font-mono text-[10px] font-semibold tracking-widest text-[#5b9bf5] uppercase">
                  {f.tag}
                </div>
                <h3 className="mb-2 text-sm font-semibold text-gray-200">
                  {f.title}
                </h3>
                <p className="text-xs leading-relaxed text-gray-500">
                  {f.description}
                </p>
              </div>
            </SpotlightCard>
          ))}
        </div>
      </div>
    </div>
  );
}
