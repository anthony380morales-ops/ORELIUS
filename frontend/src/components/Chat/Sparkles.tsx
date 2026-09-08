import { useEffect, useRef } from 'react'

/*
 * Subtle starry-night backdrop for the chat. White sparkles that gently dim
 * in and out. Canvas-based, low density, sits behind all content, and honors
 * prefers-reduced-motion (renders a still field, no animation).
 */
export default function Sparkles() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0
    let h = 0
    type Star = { x: number; y: number; r: number; base: number; spd: number; ph: number }
    let stars: Star[] = []

    const build = () => {
      w = window.innerWidth
      h = window.innerHeight
      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const count = Math.min(150, Math.max(35, Math.round((w * h) / 14000)))
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.2 + 0.3,
        base: Math.random() * 0.5 + 0.25,
        spd: Math.random() * 0.0016 + 0.0004,
        ph: Math.random() * Math.PI * 2,
      }))
    }

    let raf = 0
    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h)
      for (const s of stars) {
        const tw = reduce ? 0.8 : 0.35 + 0.65 * Math.abs(Math.sin(s.ph + t * s.spd))
        ctx.globalAlpha = s.base * tw
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = '#ffffff'
        ctx.fill()
      }
      ctx.globalAlpha = 1
      if (!reduce) raf = requestAnimationFrame(draw)
    }

    build()
    if (reduce) draw(0)
    else raf = requestAnimationFrame(draw)

    const onResize = () => {
      build()
      if (reduce) draw(0)
    }
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return <canvas ref={ref} className="oreo-stars" aria-hidden="true" />
}
