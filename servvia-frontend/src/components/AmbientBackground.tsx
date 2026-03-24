'use client';

import React, { useEffect, useRef } from 'react';

export function AmbientBackground({ isVisible = true }: { isVisible?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Configuration matching VANTA.NET
    const PARTICLE_COUNT = Math.floor(window.innerWidth / 15); // Dynamic count based on screen width
    const MAX_DISTANCE = 150; // Connection distance
    const MOUSE_RADIUS = 200; // Radius where particles react to mouse
    
    let particles: { x: number; y: number; vx: number; vy: number; radius: number }[] = [];
    let mouse = { x: -1000, y: -1000, isHovering: false };

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      
      // Re-initialize particles on major resize to fill screen
      particles = [];
      const count = Math.min(Math.floor(window.innerWidth / 15), 150); // Cap at 150 for performance
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.8,
          vy: (Math.random() - 0.5) * 0.8,
          radius: Math.random() * 1.5 + 1
        });
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.isHovering = true;
    };

    const handleMouseLeave = () => {
      mouse.isHovering = false;
    };

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseout', handleMouseLeave);
    
    // Initial setup
    resize();

    let animationFrameId: number;

    const draw = () => {
      ctx.fillStyle = '#050505'; // Deep black/gray background
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw interactive mouse glow
      if (mouse.isHovering) {
        const radGrad = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, MOUSE_RADIUS * 1.5);
        radGrad.addColorStop(0, 'rgba(220, 38, 38, 0.08)'); // Very subtle red glow
        radGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = radGrad;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }

      // Update and draw particles
      particles.forEach((p, i) => {
        // Normal movement
        p.x += p.vx;
        p.y += p.vy;

        // Bounce off walls
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        // Mouse Interaction
        if (mouse.isHovering) {
          const dx = mouse.x - p.x;
          const dy = mouse.y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          
          if (dist < MOUSE_RADIUS) {
            // Repel effect (like Vanta)
            const force = (MOUSE_RADIUS - dist) / MOUSE_RADIUS;
            p.x -= (dx / dist) * force * 1.5;
            p.y -= (dy / dist) * force * 1.5;
          }
        }

        // Draw particle dot - DIMMED DOTS as requested
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(220, 38, 38, 0.25)'; // Dimmer dots
        ctx.fill();

        // Check connections with other particles
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx2 = p.x - p2.x;
          const dy2 = p.y - p2.y;
          const dist2 = Math.sqrt(dx2 * dx2 + dy2 * dy2);

          if (dist2 < MAX_DISTANCE) {
            ctx.beginPath();
            // Opacity fades out as distance increases - BRIGHTER LINES as requested
            const opacity = 1 - (dist2 / MAX_DISTANCE);
            ctx.strokeStyle = `rgba(220, 38, 38, ${Math.min(opacity * 0.9, 1)})`; // Brighter lines
            ctx.lineWidth = window.devicePixelRatio > 1 ? 0.8 : 1.2;
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      });

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseout', handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas 
      ref={canvasRef} 
      className={`fixed inset-0 w-full h-full z-[-1] transition-opacity duration-[1500ms] ease-in-out ${isVisible ? 'opacity-100' : 'opacity-0'}`} 
      style={{ background: '#000' }}
    />
  );
}
