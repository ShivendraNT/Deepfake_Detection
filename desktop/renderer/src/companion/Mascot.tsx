import { memo, useEffect, useRef } from 'react'
import { useReducedMotion } from 'framer-motion'
import type { MotionValue } from 'framer-motion'
import * as THREE from 'three'

import type { MascotMood, Pose } from '../../../shared/contracts'
import { size as sizePx } from '../shared/tokens'

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

interface EyeRig {
  group: THREE.Group
  lid: THREE.Mesh<THREE.SphereGeometry, THREE.MeshStandardMaterial>
}

interface ArmRig {
  pivot: THREE.Group
  wrist: THREE.Group
  hand: THREE.Group
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

function randomBlinkDelay(): number {
  return 2500 + Math.random() * 3500
}

function createEye(parent: THREE.Object3D, x: number): EyeRig {
  const group = new THREE.Group()
  group.position.set(x, 0.2, 0.92)
  parent.add(group)

  const white = new THREE.Mesh(
    new THREE.SphereGeometry(0.205, 28, 20),
    new THREE.MeshPhysicalMaterial({ color: '#F8FCFF', roughness: 0.28, clearcoat: 0.35 }),
  )
  group.add(white)

  const iris = new THREE.Mesh(
    new THREE.SphereGeometry(0.112, 24, 18),
    new THREE.MeshStandardMaterial({ color: '#075985', roughness: 0.24 }),
  )
  iris.position.set(0, 0, 0.16)
  group.add(iris)

  const pupil = new THREE.Mesh(
    new THREE.SphereGeometry(0.063, 20, 16),
    new THREE.MeshStandardMaterial({ color: '#071B36', roughness: 0.16 }),
  )
  pupil.position.set(0, 0, 0.235)
  group.add(pupil)

  const highlight = new THREE.Mesh(
    new THREE.SphereGeometry(0.026, 12, 10),
    new THREE.MeshBasicMaterial({ color: '#FFFFFF' }),
  )
  highlight.position.set(-0.028, 0.035, 0.285)
  group.add(highlight)

  const lid = new THREE.Mesh(
    new THREE.SphereGeometry(0.207, 28, 20),
    new THREE.MeshStandardMaterial({ color: '#44D5DE', roughness: 0.3 }),
  )
  lid.position.z = 0.08
  lid.scale.set(1, 0.05, 0.52)
  group.add(lid)

  return { group, lid }
}

function createArm(character: THREE.Group, side: -1 | 1): ArmRig {
  const pivot = new THREE.Group()
  pivot.position.set(side * 0.72, -0.18, 0.48)
  character.add(pivot)

  const armMaterial = new THREE.MeshPhysicalMaterial({
    color: '#0284C7',
    roughness: 0.24,
    metalness: 0.04,
    clearcoat: 0.4,
  })
  const upper = new THREE.Mesh(new THREE.CylinderGeometry(0.095, 0.125, 0.34, 18), armMaterial)
  upper.position.y = -0.16
  pivot.add(upper)

  const wrist = new THREE.Group()
  wrist.position.y = -0.34
  pivot.add(wrist)
  const lower = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.095, 0.24, 16), armMaterial)
  lower.position.y = -0.12
  wrist.add(lower)

  const hand = new THREE.Group()
  hand.position.y = -0.25
  wrist.add(hand)
  const palm = new THREE.Mesh(
    new THREE.SphereGeometry(0.145, 20, 16),
    new THREE.MeshPhysicalMaterial({ color: '#38BDF8', roughness: 0.2, clearcoat: 0.5 }),
  )
  palm.scale.set(1, 0.84, 0.72)
  hand.add(palm)

  return { pivot, wrist, hand }
}

function createShield(hand: THREE.Group): THREE.Group {
  const group = new THREE.Group()
  group.position.set(0.1, 0.05, 0.16)
  group.rotation.z = -0.18
  group.scale.setScalar(0.65)

  const shape = new THREE.Shape()
  shape.moveTo(-0.2, 0.22)
  shape.lineTo(0.2, 0.22)
  shape.lineTo(0.17, -0.04)
  shape.quadraticCurveTo(0.13, -0.19, 0, -0.28)
  shape.quadraticCurveTo(-0.13, -0.19, -0.17, -0.04)
  shape.closePath()
  const shield = new THREE.Mesh(
    new THREE.ExtrudeGeometry(shape, {
      depth: 0.07,
      bevelEnabled: true,
      bevelSegments: 2,
      bevelSize: 0.025,
      bevelThickness: 0.02,
    }),
    new THREE.MeshPhysicalMaterial({ color: '#F5C542', metalness: 0.28, roughness: 0.25, clearcoat: 0.6 }),
  )
  group.add(shield)

  const emblem = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.075, 0),
    new THREE.MeshStandardMaterial({ color: '#FFF2B2', metalness: 0.2, roughness: 0.3 }),
  )
  emblem.position.set(0, 0.02, 0.1)
  group.add(emblem)
  hand.add(group)
  return group
}

function createTablet(character: THREE.Group): { group: THREE.Group; stylus: THREE.Group } {
  const group = new THREE.Group()
  group.position.set(0.31, -0.42, 0.76)
  group.rotation.z = -0.08
  group.visible = false
  character.add(group)

  const tablet = new THREE.Mesh(
    new THREE.BoxGeometry(0.48, 0.32, 0.07),
    new THREE.MeshStandardMaterial({ color: '#FFF0C2', roughness: 0.68 }),
  )
  group.add(tablet)
  const paper = new THREE.Mesh(
    new THREE.BoxGeometry(0.39, 0.23, 0.012),
    new THREE.MeshStandardMaterial({ color: '#FFFBEC', roughness: 0.75 }),
  )
  paper.position.z = 0.042
  group.add(paper)

  const stylus = new THREE.Group()
  stylus.position.set(0.12, 0.1, 0.1)
  const shaft = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.014, 0.3, 12),
    new THREE.MeshStandardMaterial({ color: '#6D5A9B', metalness: 0.2, roughness: 0.35 }),
  )
  shaft.rotation.z = -0.55
  stylus.add(shaft)
  const nib = new THREE.Mesh(
    new THREE.ConeGeometry(0.025, 0.07, 12),
    new THREE.MeshStandardMaterial({ color: '#E8B95C', metalness: 0.35, roughness: 0.3 }),
  )
  nib.position.set(-0.09, -0.13, 0)
  nib.rotation.z = -0.55
  stylus.add(nib)
  group.add(stylus)
  return { group, stylus }
}

function createZParticle(character: THREE.Group, index: number): THREE.Group {
  const group = new THREE.Group()
  group.position.set(0.52 + index * 0.12, 0.65 + index * 0.08, 0.7)
  group.visible = false
  const points = [
    new THREE.Vector3(-0.08, 0.08, 0),
    new THREE.Vector3(0.08, 0.08, 0),
    new THREE.Vector3(-0.08, -0.08, 0),
    new THREE.Vector3(0.08, -0.08, 0),
  ]
  const mesh = new THREE.Mesh(
    new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 16, 0.018, 8, false),
    new THREE.MeshBasicMaterial({ color: '#B7F3FF', transparent: true, opacity: 0.85 }),
  )
  group.add(mesh)
  character.add(group)
  return group
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
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const stateRef = useRef<LiveState>({
    pose: activePose,
    lookX: 0,
    lookY: 0,
    audioLevel,
    dragging,
    dragVelocity: dragVelocity?.get() ?? { x: 0, y: 0 },
    reducedMotion: reduced,
  })

  const tracking = Boolean(look?.near) && !reduced
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

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50)
    camera.position.set(0, 0, 4.8)

    const renderer = new THREE.WebGLRenderer({
      canvas,
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

    scene.add(new THREE.HemisphereLight('#F4FBFF', '#14517A', 2.1))
    const keyLight = new THREE.DirectionalLight('#FFFFFF', 3.2)
    keyLight.position.set(-3.5, 4.5, 5)
    scene.add(keyLight)
    const rimLight = new THREE.DirectionalLight('#67E8F9', 1.8)
    rimLight.position.set(3, 0.8, -2)
    scene.add(rimLight)

    const character = new THREE.Group()
    scene.add(character)

    const body = new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 48),
      new THREE.MeshPhysicalMaterial({
        color: '#38BDF8',
        roughness: 0.2,
        metalness: 0.1,
        clearcoat: 0.6,
        clearcoatRoughness: 0.16,
      }),
    )
    body.scale.set(1, 1.08, 0.9)
    body.position.y = -0.02
    character.add(body)

    const eyes = [createEye(body, -0.37), createEye(body, 0.37)]
    const arms = [createArm(character, -1), createArm(character, 1)]
    const [leftArm, rightArm] = arms
    const shield = createShield(rightArm.hand)
    const tablet = createTablet(character)
    const zParticles = [0, 1, 2].map((index) => createZParticle(character, index))

    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(1.2, 0.022, 12, 64),
      new THREE.MeshBasicMaterial({ color: '#F4C95D', transparent: true, opacity: 0.75 }),
    )
    halo.position.set(0, 0, -0.12)
    halo.visible = false
    character.add(halo)

    const soundRings = [-1, 1].map((side) => {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.18, 0.018, 8, 32),
        new THREE.MeshBasicMaterial({ color: '#9CECF5', transparent: true, opacity: 0.35 }),
      )
      ring.position.set(side * 1.03, 0.08, 0.36)
      ring.visible = false
      character.add(ring)
      return ring
    })

    const sparkles = [-1, 0, 1].map((index) => {
      const sparkle = new THREE.Mesh(
        new THREE.OctahedronGeometry(0.075 + Math.abs(index) * 0.018, 0),
        new THREE.MeshBasicMaterial({ color: '#FFE08A', transparent: true, opacity: 0.9 }),
      )
      sparkle.position.set(index * 0.8, 0.5 + Math.abs(index) * 0.16, 0.72)
      sparkle.visible = false
      character.add(sparkle)
      return sparkle
    })

    const mouthPath = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-0.17, -0.22, 0.97),
      new THREE.Vector3(0, -0.28, 1),
      new THREE.Vector3(0.17, -0.22, 0.97),
    ])
    const mouth = new THREE.Mesh(
      new THREE.TubeGeometry(mouthPath, 18, 0.022, 8, false),
      new THREE.MeshStandardMaterial({ color: '#075985', roughness: 0.35 }),
    )
    body.add(mouth)

    let frameId = 0
    let blinkStartAt = -1
    let nextBlinkAt = performance.now() + randomBlinkDelay()
    let doubleBlinkAt: number | null = null
    let previousPose = activePose
    let poseChangedAt = performance.now()
    let previouslyDragging = false
    let lastDragStrength = 0
    let dropStartedAt = 0
    let dropStrength = 0
    let poseStretchY = 1
    const targetQuaternion = new THREE.Quaternion()
    const targetEuler = new THREE.Euler(0, 0, 0, 'XYZ')

    const renderFrame = (now: number): void => {
      frameId = window.requestAnimationFrame(renderFrame)
      if (document.visibilityState === 'hidden') return

      const state = stateRef.current
      const time = now / 1000
      const sleeping = state.pose === 'sleep' || state.pose === 'off'
      const period = sleeping ? 4.5 : state.pose === 'relief' ? 2.8 : 3.6
      const breath = state.reducedMotion ? 0 : Math.sin((time * Math.PI * 2) / period)
      if (state.pose !== previousPose) {
        previousPose = state.pose
        poseChangedAt = now
      }
      const catching = state.pose === 'catch'
      const targetPoseStretchY = catching ? 1.08 : 1
      poseStretchY += (targetPoseStretchY - poseStretchY) * 0.12
      const dragSpeed = Math.hypot(state.dragVelocity.x, state.dragVelocity.y)
      const dragStretch = state.dragging ? clamp((dragSpeed / 36) * 0.16, 0, 0.16) : 0
      if (state.dragging) lastDragStrength = Math.max(lastDragStrength, dragStretch)
      if (previouslyDragging && !state.dragging) {
        dropStartedAt = now
        dropStrength = lastDragStrength
        lastDragStrength = 0
      }
      previouslyDragging = state.dragging
      const dropElapsed = Math.max(0, (now - dropStartedAt) / 1000)
      const dropBounce = !state.dragging && dropStartedAt > 0
        ? Math.exp(-dropElapsed * 8) * Math.sin(dropElapsed * 20) * dropStrength
        : 0
      const stretch = dragStretch + dropBounce
      body.scale.x = 1 - breath * 0.015 - stretch * 0.2
      body.scale.y = 1.08 * poseStretchY + breath * 0.03 + stretch * 0.5
      body.scale.z = 0.9 + breath * 0.008 + stretch * 0.15

      const alertProgress = clamp((now - poseChangedAt) / 520, 0, 1)
      const alertHop = state.pose === 'alert' && !state.reducedMotion
        ? Math.sin(alertProgress * Math.PI) * 0.18
        : 0
      const targetY = (sleeping ? -0.08 : 0) + alertHop
      character.position.y += (targetY - character.position.y) * 0.12
      const cameraTilt = state.pose === 'listen' ? 0.018 : state.pose === 'think' ? -0.014 : 0
      camera.rotation.z += (cameraTilt - camera.rotation.z) * 0.12
      const dragTilt = state.dragging && dragSpeed > 0.1
        ? Math.atan2(-state.dragVelocity.y, state.dragVelocity.x) - Math.PI / 2
        : null
      const targetTilt = dragTilt ?? (state.pose === 'listen' ? -0.05 : state.pose === 'think' ? 0.035 : 0)
      character.rotation.z += (targetTilt - character.rotation.z) * 0.12

      const wave = state.pose === 'wave' && !state.reducedMotion
      const leftArmTarget = catching
        ? -2.6
        : state.pose === 'alert'
          ? -0.05
          : state.pose === 'listen'
            ? -2.25
            : 0.25
      const rightArmTarget = catching
        ? 2.6
        : state.pose === 'alert'
          ? 2.25
          : wave
            ? 0.55 + Math.sin(time * 4.2) * 0.44
            : state.pose === 'write'
              ? 0.95
              : 0.25
      leftArm.pivot.rotation.z += (leftArmTarget - leftArm.pivot.rotation.z) * 0.12
      rightArm.pivot.rotation.z += (rightArmTarget - rightArm.pivot.rotation.z) * 0.12
      const leftAnchorY = catching ? -0.06 : -0.18
      const rightAnchorY = catching ? -0.06 : state.pose === 'write' ? -0.28 : -0.18
      leftArm.pivot.position.y += (leftAnchorY - leftArm.pivot.position.y) * 0.12
      rightArm.pivot.position.y += (rightAnchorY - rightArm.pivot.position.y) * 0.12
      const leftAnchorX = catching ? -0.76 : -0.72
      const rightAnchorX = catching ? 0.76 : 0.72
      leftArm.pivot.position.x += (leftAnchorX - leftArm.pivot.position.x) * 0.12
      rightArm.pivot.position.x += (rightAnchorX - rightArm.pivot.position.x) * 0.12
      leftArm.wrist.rotation.z += ((catching ? -0.18 : 0) - leftArm.wrist.rotation.z) * 0.12
      const wristLag = wave && !state.reducedMotion ? Math.sin(time * 4.2 - 0.55) * 0.2 : 0
      rightArm.wrist.rotation.z += (wristLag - rightArm.wrist.rotation.z) * 0.18

      shield.visible = state.pose === 'alert'
      tablet.group.visible = state.pose === 'write'
      tablet.stylus.rotation.y = Math.sin(time * 4.8) * 0.2
      tablet.stylus.position.x = 0.12 + Math.sin(time * 4.8) * 0.045
      halo.visible = state.pose === 'alert'
      const haloPulse = 1 + (state.pose === 'alert' && !state.reducedMotion ? Math.sin(time * 3) * 0.045 : 0)
      halo.scale.setScalar(haloPulse)

      const listening = state.pose === 'listen'
      const level = state.audioLevel
      for (const ring of soundRings) {
        ring.visible = listening
        const pulse = 1 + level * 1.2 + Math.sin(time * 5) * 0.035
        ring.scale.setScalar(pulse)
        ;(ring.material as THREE.MeshBasicMaterial).opacity = listening ? 0.22 + level * 0.55 : 0
      }

      const relieved = state.pose === 'relief'
      sparkles.forEach((sparkle, index) => {
        sparkle.visible = relieved
        sparkle.rotation.y += 0.04 + index * 0.01
        sparkle.scale.setScalar(relieved ? 0.85 + Math.sin(time * 4 + index) * 0.2 : 0.01)
      })
      zParticles.forEach((particle, index) => {
        particle.visible = sleeping
        const phase = ((time * 0.45 + index * 0.31) % 1 + 1) % 1
        particle.position.y = 0.65 + index * 0.08 + phase * 0.42
        const mesh = particle.children[0] as THREE.Mesh
        ;(mesh.material as THREE.MeshBasicMaterial).opacity = sleeping ? 0.85 * (1 - phase) : 0
      })

      targetEuler.set(
        state.pose === 'alert' ? 0 : -state.lookY * 0.055,
        state.pose === 'alert' ? 0 : state.lookX * 0.055,
        0,
      )
      targetQuaternion.setFromEuler(targetEuler)
      const eyeHeight = catching || state.pose === 'alert' ? 1.08 : state.pose === 'think' ? 0.92 : 1
      for (const eye of eyes) {
        eye.group.quaternion.slerp(targetQuaternion, 0.15)
        eye.group.scale.y += (eyeHeight - eye.group.scale.y) * 0.12
      }

      if (!sleeping) {
        if (doubleBlinkAt !== null) {
          if (now >= doubleBlinkAt) {
            blinkStartAt = now
            doubleBlinkAt = null
            nextBlinkAt = now + randomBlinkDelay()
          }
        } else if (now >= nextBlinkAt) {
          blinkStartAt = now
          if (Math.random() < 0.2) doubleBlinkAt = now + 250
          else nextBlinkAt = now + randomBlinkDelay()
        }
      }

      const blinkProgress = blinkStartAt < 0 ? 1 : clamp((now - blinkStartAt) / 120, 0, 1)
      const blinkScale = blinkProgress < 0.5
        ? THREE.MathUtils.lerp(0.05, 1, blinkProgress * 2)
        : THREE.MathUtils.lerp(1, 0.05, (blinkProgress - 0.5) * 2)
      for (const eye of eyes) {
        eye.lid.scale.y = sleeping ? 1 : blinkScale
      }

      renderer.render(scene, camera)
    }

    frameId = window.requestAnimationFrame(renderFrame)

    return () => {
      window.cancelAnimationFrame(frameId)
      scene.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) return
        object.geometry.dispose()
        const materials = Array.isArray(object.material) ? object.material : [object.material]
        for (const material of materials) material.dispose()
      })
      renderer.dispose()
      renderer.forceContextLoss()
    }
  }, [])

  return (
    <div
      style={{
        width: renderedSize,
        height: renderedSize,
        position: 'relative',
        overflow: 'visible',
        userSelect: 'none',
      }}
      role="img"
      aria-label={`Satya living 3D mascot, ${activePose}`}
    >
      <canvas
        ref={canvasRef}
        width={200}
        height={200}
        aria-hidden="true"
        style={{ width: '100%', height: '100%', display: 'block', pointerEvents: 'none' }}
      />
    </div>
  )
})

export default Mascot
