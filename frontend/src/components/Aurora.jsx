import { useEffect, useRef } from 'react';
import { Mesh, Program, Renderer, Triangle } from 'ogl';
import './Aurora.css';

const DEFAULT_COLORS = ['#6C63FF', '#A78BFA', '#4F46E5'];

function hexToRgb(hex) {
  const value = hex.replace('#', '');
  const normalized = value.length === 3 ? value.split('').map((part) => part + part).join('') : value;
  return [0, 2, 4].map((index) => parseInt(normalized.slice(index, index + 2), 16) / 255);
}

export function Aurora({
  colorStops = DEFAULT_COLORS,
  amplitude = 0.5,
  blend = 0.35,
  speed = 0.25,
  lightMode = true,
}) {
  const hostRef = useRef(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const renderer = new Renderer({ alpha: true, antialias: true, dpr: Math.min(window.devicePixelRatio, 2) });
    const gl = renderer.gl;
    gl.canvas.className = 'aurora-canvas';
    host.appendChild(gl.canvas);

    const colors = [...colorStops, ...DEFAULT_COLORS].slice(0, 3).map(hexToRgb);
    const program = new Program(gl, {
      vertex: `
        attribute vec2 position;
        varying vec2 vUv;
        void main() {
          vUv = position * 0.5 + 0.5;
          gl_Position = vec4(position, 0.0, 1.0);
        }
      `,
      fragment: `
        precision highp float;
        uniform float uTime;
        uniform float uAmplitude;
        uniform float uBlend;
        uniform float uLightMode;
        uniform vec3 uColor1;
        uniform vec3 uColor2;
        uniform vec3 uColor3;
        varying vec2 vUv;

        void main() {
          vec2 uv = vUv;
          float waveA = sin(uv.x * 4.6 + uTime * 0.65) * 0.10;
          float waveB = sin(uv.x * 8.0 - uTime * 0.42 + 1.8) * 0.055;
          float band = smoothstep(0.05, 0.88, uv.y + waveA + waveB * uAmplitude);
          float edgeFade = smoothstep(0.02, 0.42, uv.x) * (1.0 - smoothstep(0.58, 1.0, uv.x));
          float verticalFade = smoothstep(0.02, 0.34, uv.y) * (1.0 - smoothstep(0.72, 1.0, uv.y));
          vec3 first = mix(uColor1, uColor2, smoothstep(0.12, 0.62, uv.x));
          vec3 color = mix(first, uColor3, smoothstep(0.42, 0.94, uv.x + band * 0.18));
          float alpha = band * edgeFade * verticalFade * uBlend * (uLightMode > 0.5 ? 0.72 : 1.0);
          gl_FragColor = vec4(color, alpha);
        }
      `,
      uniforms: {
        uTime: { value: 0 },
        uAmplitude: { value: amplitude },
        uBlend: { value: blend },
        uLightMode: { value: lightMode ? 1 : 0 },
        uColor1: { value: colors[0] },
        uColor2: { value: colors[1] },
        uColor3: { value: colors[2] },
      },
    });
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });
    let frame;
    let startedAt = performance.now();

    const resize = () => {
      const { width, height } = host.getBoundingClientRect();
      renderer.setSize(Math.max(1, width), Math.max(1, height));
    };
    const render = (now) => {
      program.uniforms.uTime.value = ((now - startedAt) / 1000) * speed;
      renderer.render({ scene: mesh });
      frame = requestAnimationFrame(render);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();
    frame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      gl.canvas.remove();
    };
  }, [amplitude, blend, colorStops.join(','), lightMode, speed]);

  return <div className="aurora" ref={hostRef} aria-hidden="true" />;
}
