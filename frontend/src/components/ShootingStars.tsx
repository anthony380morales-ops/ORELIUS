import { useEffect, useRef } from 'react'

interface ShootingStar {
  x: number
  y: number
  length: number
  speed: number
  opacity: number
  thickness: number
  angle: number
}

export default function ShootingStars() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas size
    const resizeCanvas = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resizeCanvas()
    window.addEventListener('resize', resizeCanvas)

    const shootingStars: ShootingStar[] = []
    let lastSpawnTime = 0

    // Create a new shooting star
    const createShootingStar = () => {
      const startX = Math.random() * canvas.width
      const startY = Math.random() * (canvas.height * 0.4) // Top 40% of screen

      shootingStars.push({
        x: startX,
        y: startY,
        length: Math.random() * 80 + 60, // Length of trail
        speed: Math.random() * 8 + 12, // Speed
        opacity: 1,
        thickness: Math.random() * 2 + 1,
        angle: Math.PI / 4 + (Math.random() - 0.5) * 0.3, // Roughly 45 degrees with variation
      })
    }

    // Animation
    let animationId: number
    const animate = (timestamp: number) => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Spawn new shooting star every 5 seconds
      if (timestamp - lastSpawnTime > 5000) {
        createShootingStar()
        lastSpawnTime = timestamp
      }

      // Update and draw shooting stars
      for (let i = shootingStars.length - 1; i >= 0; i--) {
        const star = shootingStars[i]

        // Move star
        star.x += Math.cos(star.angle) * star.speed
        star.y += Math.sin(star.angle) * star.speed

        // Fade out
        star.opacity -= 0.008

        // Remove if off-screen or faded
        if (
          star.opacity <= 0 ||
          star.x > canvas.width + 100 ||
          star.y > canvas.height + 100
        ) {
          shootingStars.splice(i, 1)
          continue
        }

        // Draw shooting star with trail
        const gradient = ctx.createLinearGradient(
          star.x,
          star.y,
          star.x - Math.cos(star.angle) * star.length,
          star.y - Math.sin(star.angle) * star.length
        )

        gradient.addColorStop(0, `rgba(255, 255, 255, ${star.opacity})`)
        gradient.addColorStop(0.3, `rgba(147, 197, 253, ${star.opacity * 0.8})`)
        gradient.addColorStop(0.6, `rgba(96, 165, 250, ${star.opacity * 0.5})`)
        gradient.addColorStop(1, 'rgba(59, 130, 246, 0)')

        ctx.beginPath()
        ctx.moveTo(star.x, star.y)
        ctx.lineTo(
          star.x - Math.cos(star.angle) * star.length,
          star.y - Math.sin(star.angle) * star.length
        )
        ctx.strokeStyle = gradient
        ctx.lineWidth = star.thickness
        ctx.lineCap = 'round'
        ctx.stroke()

        // Add glow effect to the head
        ctx.beginPath()
        ctx.arc(star.x, star.y, star.thickness * 2, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255, 255, 255, ${star.opacity * 0.8})`
        ctx.shadowBlur = 20
        ctx.shadowColor = `rgba(147, 197, 253, ${star.opacity})`
        ctx.fill()
        ctx.shadowBlur = 0
      }

      animationId = requestAnimationFrame(animate)
    }

    // Start animation
    animationId = requestAnimationFrame(animate)

    return () => {
      window.removeEventListener('resize', resizeCanvas)
      cancelAnimationFrame(animationId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-[5]"
    />
  )
}
