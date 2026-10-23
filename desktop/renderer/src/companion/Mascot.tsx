import { memo, useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import type { MotionValue } from 'framer-motion'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

import type { MascotMood, Pose } from '../../../shared/contracts'
import mascot3dImg from '../assets/mascot_3d.png'
import mascotAlertImg from '../assets/mascot_alert.png'
import mascotCatchImg from '../assets/mascot_catch.png'
import mascotListenImg from '../assets/mascot_listen.png'
import mascotReliefImg from '../assets/mascot_relief.png'
import mascotSleepImg from '../assets/mascot_sleep.png'
import mascotThinkImg from '../assets/mascot_think.png'
import mascotWaveImg from '../assets/mascot_wave.png'
import mascotWriteImg from '../assets/mascot_write.png'
import satyaGlbUrl from '../assets/satya.glb'
import { color, size as sizePx } from '../shared/tokens'
import { Accessories } from './accessories'
import { POSES } from './poses'
import { BLINK_MS, useBlink } from './useBlink'

// Patch WebGL shader precision format prototype for macOS Electron transparent windows
if (typeof window !== 'undefined') {
  const patchPrecision = (proto: any) => {
    if (!proto || typeof proto.getShaderPrecisionFormat !== 'function') return
    const orig = proto.getShaderPrecisionFormat
    proto.getShaderPrecisionFormat = function (shaderType: number, precisionType: number) {
      try {
        const res = orig.call(this, shaderType, precisionType)
        if (res && typeof res.precision === 'number' && res.precision > 0) return res
      } catch {
        // fallback
      }
      return { precision: 23, rangeMin: 127, rangeMax: 127 }
    }
  }
  if ('WebGLRenderingContext' in window) patchPrecision((window as any).WebGLRenderingContext?.prototype)
  if ('WebGL2RenderingContext' in window) patchPrecision((window as any).WebGL2RenderingContext?.prototype)
}

export type MascotSize = keyof typeof sizePx

export interface MascotProps {
  pose?: Pose
  mood?: MascotMood | string
  alert?: boolean
  audioLevel?: number
  look?: { dx: number; dy: number; near: boolean }
  dragging?: boolean
  dragVelocity?: MotionValue<{ x: number; y: number }>
  size?: number | MascotSize
  reducedMotion?: boolean
}

const MOOD_TO_POSE: Record<string, Pose> = {
  sleepy: 'sleep',
  attentive: 'idle',
  focused: 'think',
  calm_alert: 'alert',
  writing: 'write',
  off: 'off',
}

const POSE_IMAGES: Record<Pose, string> = {
  sleep: mascotSleepImg,
  idle: mascot3dImg,
  listen: mascotListenImg,
  think: mascotThinkImg,
  alert: mascotAlertImg,
  relief: mascotReliefImg,
  write: mascotWriteImg,
  catch: mascotCatchImg,
  wave: mascotWaveImg,
  off: mascotSleepImg,
}

interface LiveState {
  pose: Pose
  lookX: number
  lookY: number
  audioLevel: number
  dragging: boolean
  dragVelocity: { x: number; y: number }
  reducedMotion: boolean
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

const Mascot = memo(function Mascot({
  pose,
  mood,
  audioLevel = 0,
  look,
  dragging = false,
  dragVelocity,
  size = 'M',
  reducedMotion,
}: MascotProps) {
  const activePose: Pose = pose ?? (mood ? MOOD_TO_POSE[mood] ?? 'idle' : 'idle')
  const systemReducedMotion = useReducedMotion()
  const reduced = Boolean(systemReducedMotion) || Boolean(reducedMotion)
  const renderedSize = typeof size === 'number' ? size : sizePx[size]
  const blinkKey = useBlink(activePose, reduced)
  const supportsBlink = ['idle', 'listen', 'alert', 'catch'].includes(activePose)

  const [webglReady, setWebglReady] = useState(false)
  const [webglFailed, setWebglFailed] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const tracking = Boolean(look?.near) && !reduced
  const stateRef = useRef<LiveState>({
    pose: activePose,
    lookX: 0,
    lookY: 0,
    audioLevel,
    dragging,
    dragVelocity: dragVelocity?.get() ?? { x: 0, y: 0 },
    reducedMotion: reduced,
  })

  stateRef.current = {
    pose: activePose,
    lookX: tracking ? clamp((look?.dx ?? 0) / 35, -5, 5) : 0,
    lookY: tracking ? clamp((look?.dy ?? 0) / 35, -4, 4) : 0,
    audioLevel: clamp(audioLevel, 0, 1),
    dragging,
    dragVelocity: stateRef.current.dragVelocity,
    reducedMotion: reduced,
  }

  useEffect(() => {
    if (!dragVelocity) return
    return dragVelocity.on('change', (velocity) => {
      stateRef.current.dragVelocity = velocity
    })
  }, [dragVelocity])

  // Preload fallback images
  useEffect(() => {
    for (const src of Object.values(POSE_IMAGES)) {
      const img = new Image()
      img.src = src
    }
  }, [])

  // Three.js 3D Model Loading and Procedural Rig Loop
  useEffect(() => {
    if (webglFailed) return
    const canvas = canvasRef.current
    if (!canvas) return

    let renderer: THREE.WebGLRenderer | null = null
    let frameId = 0
    let scene: THREE.Scene | null = null

    const onContextLost = (e: Event) => {
      e.preventDefault()
      console.warn('[Satya] WebGL context lost; falling back to 2D image')
      setWebglFailed(true)
    }
    canvas.addEventListener('webglcontextlost', onContextLost)

    try {
      const gl =
        canvas.getContext('webgl2', {
          alpha: true,
          antialias: true,
          powerPreference: 'high-performance',
        }) ||
        canvas.getContext('webgl', {
          alpha: true,
          antialias: true,
          powerPreference: 'high-performance',
        })

      if (gl && typeof gl.getShaderPrecisionFormat === 'function') {
        const orig = gl.getShaderPrecisionFormat.bind(gl)
        gl.getShaderPrecisionFormat = (st: number, pt: number) => {
          try {
            const res = orig(st, pt)
            if (res && typeof res.precision === 'number' && res.precision > 0) return res
          } catch {
            // fallback
          }
          return { precision: 23, rangeMin: 127, rangeMax: 127 }
        }
      }

      scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50)
      camera.position.set(0, 0, 4.6)

      renderer = new THREE.WebGLRenderer({
        canvas,
        context: (gl as WebGLRenderingContext | WebGL2RenderingContext) || undefined,
        alpha: true,
        antialias: true,
        powerPreference: 'high-performance',
      })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
      renderer.setSize(200, 200, false)
      renderer.setClearColor(0x000000, 0)
      renderer.outputColorSpace = THREE.SRGBColorSpace
      renderer.toneMapping = THREE.ACESFilmicToneMapping
      renderer.toneMappingExposure = 1.15

      // Studio Lighting for Satya's 3D Blue Blob
      scene.add(new THREE.HemisphereLight('#FFFFFF', '#082F49', 2.4))

      const keyLight = new THREE.DirectionalLight('#FFFFFF', 2.6)
      keyLight.position.set(-2.5, 3.5, 4)
      scene.add(keyLight)

      const rimLight = new THREE.DirectionalLight('#38BDF8', 2.0)
      rimLight.position.set(2.8, 1.2, -2.5)
      scene.add(rimLight)

      const fillLight = new THREE.DirectionalLight('#BAE6FD', 1.0)
      fillLight.position.set(0, -2.5, 2)
      scene.add(fillLight)

      const rootGroup = new THREE.Group()
      scene.add(rootGroup)

      const modelPivot = new THREE.Group()
      rootGroup.add(modelPivot)

      let baseScale = 2.4
      let isModelLoaded = false

      // Load satya.glb
      const loader = new GLTFLoader()
      loader.load(
        satyaGlbUrl,
        (gltf) => {
          const model = gltf.scene

          // Polish model: compute smooth vertex normals & upgrade material to tactile physical sheen
          model.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh
              if (mesh.geometry) {
                mesh.geometry.computeVertexNormals()
              }
              const oldMat = mesh.material as THREE.MeshStandardMaterial
              const polishedMat = new THREE.MeshPhysicalMaterial({
                map: oldMat?.map || null,
                color: oldMat?.color || new THREE.Color('#38BDF8'),
                roughness: 0.28,
                metalness: 0.04,
                clearcoat: 0.65,
                clearcoatRoughness: 0.16,
              })
              mesh.material = polishedMat
            }
          })

          // Center geometry at origin
          const box = new THREE.Box3().setFromObject(model)
          const center = new THREE.Vector3()
          box.getCenter(center)
          model.position.sub(center)

          const sizeVec = new THREE.Vector3()
          box.getSize(sizeVec)
          const maxDim = Math.max(sizeVec.x, sizeVec.y, sizeVec.z)
          baseScale = 2.45 / (maxDim || 1)
          modelPivot.scale.setScalar(baseScale)

          modelPivot.add(model)
          isModelLoaded = true
          setWebglReady(true)
        },
        undefined,
        (err) => {
          console.warn('[Satya] satya.glb load failed, using 2D fallback:', err)
          setWebglFailed(true)
        },
      )

      // Interactive procedural animation state
      let rotX = 0
      let rotY = 0
      let rotZ = 0
      let targetRotX = 0
      let targetRotY = 0
      let targetRotZ = 0
      let posY = 0
      let targetPosY = 0
      let startTime = performance.now()

      const renderFrame = (now: number) => {
        if (!renderer || !scene) return
        const t = (now - startTime) * 0.001
        const state = stateRef.current

        if (isModelLoaded && !state.reducedMotion) {
          // 1. Organic micro-breathing loop (volume-preserving squash & stretch)
          let breathSpeed = 2.2
          let breathIntensity = 0.032
          if (state.pose === 'sleep') {
            breathSpeed = 1.4
            breathIntensity = 0.045
          } else if (state.pose === 'alert') {
            breathSpeed = 3.6
            breathIntensity = 0.02
          } else if (state.pose === 'wave') {
            breathSpeed = 2.8
            breathIntensity = 0.035
          }
          const breath = Math.sin(t * breathSpeed) * breathIntensity
          const breathSquash = Math.cos(t * breathSpeed) * (breathIntensity * 0.5)

          let scaleX = baseScale * (1 - breathSquash)
          let scaleY = baseScale * (1 + breath)
          let scaleZ = baseScale * (1 - breathSquash)

          // 2. Cursor Gaze Tracking
          targetRotY = (state.lookX / 5) * 0.42
          targetRotX = (-state.lookY / 4) * 0.32
          targetRotZ = 0
          targetPosY = 0

          // 3. Pose-specific procedural offsets
          if (state.pose === 'sleep') {
            targetRotX += 0.2
            targetPosY = -0.12
            targetRotY *= 0.25
          } else if (state.pose === 'listen') {
            const listenTilt = 0.18 + Math.sin(t * 2.4) * 0.04
            targetRotZ = -listenTilt
            targetRotY += 0.12
          } else if (state.pose === 'alert') {
            targetPosY = 0.15 + Math.sin(t * 4.0) * 0.03
            scaleX *= 1.04
            scaleY *= 1.04
          } else if (state.pose === 'wave') {
            const waveOscillation = Math.sin(t * 5.0) * 0.18
            targetRotZ = waveOscillation
            targetPosY = Math.abs(Math.sin(t * 5.0)) * 0.06
          } else if (state.pose === 'think') {
            targetRotZ = Math.sin(t * 1.6) * 0.08
            targetRotY += Math.cos(t * 1.4) * 0.12
            targetPosY = Math.sin(t * 1.8) * 0.04
          } else if (state.pose === 'catch') {
            targetPosY = 0.14
            scaleY *= 1.08
            scaleX *= 0.98
          } else if (state.pose === 'relief') {
            targetPosY = -0.05 + Math.sin(t * 2.0) * 0.05
          } else if (state.pose === 'off') {
            scaleY *= 0.92
            targetPosY = -0.15
          }

          // 4. Drag feedback
          if (state.dragging) {
            scaleY *= 0.94
            scaleX *= 1.04
            targetRotZ += clamp((state.dragVelocity?.x || 0) * 0.0015, -0.25, 0.25)
          }

          // 5. Spring smoothing
          rotX += (targetRotX - rotX) * 0.12
          rotY += (targetRotY - rotY) * 0.12
          rotZ += (targetRotZ - rotZ) * 0.12
          posY += (targetPosY - posY) * 0.14

          modelPivot.rotation.x = rotX
          modelPivot.rotation.y = rotY
          modelPivot.rotation.z = rotZ
          modelPivot.position.y = posY
          modelPivot.scale.set(scaleX, scaleY, scaleZ)
        }

        try {
          renderer.render(scene, camera)
          frameId = window.requestAnimationFrame(renderFrame)
        } catch (renderError) {
          console.warn('[Satya] Three.js render frame error:', renderError)
          setWebglFailed(true)
        }
      }

      frameId = window.requestAnimationFrame(renderFrame)
    } catch (err) {
      console.warn('[Satya] Three.js WebGL initialization failed, using 2D fallback:', err)
      setWebglFailed(true)
    }

    return () => {
      canvas.removeEventListener('webglcontextlost', onContextLost)
      if (frameId) window.cancelAnimationFrame(frameId)
      if (scene) {
        scene.traverse((object) => {
          if (!(object as THREE.Mesh).isMesh) return
          const mesh = object as THREE.Mesh
          mesh.geometry?.dispose()
          const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
          for (const m of materials) m?.dispose()
        })
      }
      if (renderer) {
        renderer.dispose()
      }
    }
  }, [webglFailed])

  const auraColor =
    activePose === 'alert'
      ? color.hold
      : activePose === 'listen'
      ? color.watch
      : activePose === 'relief'
      ? color.good
      : activePose === 'write'
      ? color.write
      : color.verify

  const showAura = ['alert', 'relief', 'listen', 'write', 'catch'].includes(activePose)
  const listenAura = 0.25 + Math.min(1, Math.max(0, audioLevel)) * 0.45
  const auraOpacity = activePose === 'alert' ? 0.65 : activePose === 'listen' ? listenAura : 0.4

  return (
    <div
      style={{
        width: renderedSize,
        height: renderedSize,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        userSelect: 'none',
        overflow: 'visible',
      }}
      role="img"
      aria-label={`Satya 3D mascot, ${activePose}`}
    >
      {/* SVG Halo Aura Ring Behind 3D Character */}
      <svg
        viewBox="0 0 200 200"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          overflow: 'visible',
          pointerEvents: 'none',
        }}
      >
        <motion.circle
          cx={100}
          cy={100}
          r={96}
          fill="none"
          stroke={auraColor}
          strokeWidth={4}
          initial={{ opacity: 0 }}
          animate={{
            opacity: showAura ? auraOpacity : 0,
            scale: activePose === 'alert' && !reduced ? [1, 1.06, 1] : 1,
          }}
          transition={
            activePose === 'alert' && !reduced
              ? { duration: 1.0, repeat: Infinity, ease: 'easeInOut' }
              : { duration: 0.3 }
          }
          style={{ opacity: 0, transformBox: 'view-box', transformOrigin: '100px 100px' }}
        />

        {/* Ambient SVG Accessories for Poses that Benefit from Extra Visual Flourish */}
        <motion.g
          id="accessories"
          style={{ transformBox: 'view-box', transformOrigin: '100px 100px' }}
        >
          {activePose === 'sleep' ? (
            <Accessories pose="sleep" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : activePose === 'listen' ? (
            <Accessories pose="listen" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : activePose === 'relief' ? (
            <Accessories pose="relief" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : activePose === 'think' ? (
            <Accessories pose="think" audioLevel={audioLevel} reducedMotion={reduced} />
          ) : null}
        </motion.g>
      </svg>

      {/* 3D Living Pet Canvas */}
      <canvas
        ref={canvasRef}
        width={200}
        height={200}
        aria-hidden="true"
        style={{
          width: '100%',
          height: '100%',
          display: webglReady && !webglFailed ? 'block' : 'none',
          pointerEvents: 'none',
          filter: 'drop-shadow(0 8px 16px rgba(20,16,40,0.22))',
        }}
      />

      {/* Smooth 2D Fallback shown while 3D is loading or if WebGL is disabled */}
      {(!webglReady || webglFailed) && (
        <img
          src={POSE_IMAGES[activePose] ?? mascot3dImg}
          alt={`Satya 3D Mascot - ${activePose}`}
          draggable={false}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'contain',
            pointerEvents: 'none',
            display: 'block',
            filter: 'drop-shadow(0 6px 14px rgba(20,16,40,0.22))',
          }}
        />
      )}

      {/* Eyelid Blink Layer */}
      {supportsBlink && blinkKey > 0 && activePose !== 'sleep' ? (
        <svg
          viewBox="0 0 200 200"
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            overflow: 'visible',
            pointerEvents: 'none',
            zIndex: 2,
          }}
        >
          <motion.ellipse
            key={`left-${blinkKey}`}
            cx={64.5}
            cy={113}
            rx={23}
            ry={24}
            fill="#44D5DE"
            initial={{ scaleY: 0 }}
            animate={{ scaleY: [0, 1, 0] }}
            transition={{ duration: BLINK_MS / 1000, ease: 'easeInOut' }}
            style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
          />
          <motion.ellipse
            key={`right-${blinkKey}`}
            cx={133}
            cy={115}
            rx={23}
            ry={24}
            fill="#44D5DE"
            initial={{ scaleY: 0 }}
            animate={{ scaleY: [0, 1, 0] }}
            transition={{ duration: BLINK_MS / 1000, ease: 'easeInOut' }}
            style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
          />
        </svg>
      ) : null}
    </div>
  )
})

export default Mascot
