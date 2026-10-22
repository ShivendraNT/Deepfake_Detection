/** Calm ambient background. No flashing; CSS respects prefers-reduced-motion. */
export default function Aurora() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-[30px]">
      <div className="absolute -left-20 -top-24 h-64 w-64 animate-aurora-drift rounded-full bg-mint-500/15 blur-3xl" />
      <div className="absolute -bottom-28 -right-16 h-72 w-72 animate-aurora-drift rounded-full bg-sky-500/10 blur-3xl [animation-delay:-6s]" />
      <div className="absolute left-1/3 top-1/2 h-40 w-40 animate-aurora-drift rounded-full bg-violet-500/10 blur-3xl [animation-delay:-11s]" />
      <div
        className="absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.55) 1px, transparent 0)',
          backgroundSize: '18px 18px',
        }}
      />
    </div>
  )
}
