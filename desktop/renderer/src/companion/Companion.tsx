import { AnimatePresence } from 'framer-motion'
import { useCallback } from 'react'

import AlertCard from './AlertCard'
import Aurora from './Aurora'
import ClipboardCard from './ClipboardCard'
import ConsentCard from './ConsentCard'
import Mascot from './Mascot'
import ScribeCard from './ScribeCard'
import StatusBar from './StatusBar'
import StatusBubble from './StatusBubble'
import Toast from './Toast'
import { useCompanion } from './useCompanion'

export default function Companion(): JSX.Element {
  const {
    status,
    modeLabel,
    alert,
    lastDraft,
    connection,
    busy,
    toast,
    consentOpen,
    consentSource,
    dismissed,
    soundOn,
    clipboard,
    start,
    stop,
    demo,
    hide,
    draft,
    openWorkspace,
    copyRefusal,
    checkClipboard,
    openConsent,
    closeConsent,
    setConsentSource,
    dismiss,
    toggleSound,
    toggleSleep,
    notify,
  } = useCompanion()

  const handleAction = useCallback(
    (actionId: string) => {
      if (actionId === 'verify_callback' || actionId === 'copy_refusal') {
        copyRefusal()
        return
      }
      if (actionId === 'draft_section63') {
        draft('section63')
        return
      }
      if (actionId === 'draft_1930') {
        draft('helpline_1930')
        return
      }
      if (actionId === 'open_workspace') {
        openWorkspace()
        return
      }
      notify(`Action ${actionId} noted`, 'info')
    },
    [copyRefusal, draft, openWorkspace, notify],
  )

  const isAlerting = Boolean(alert && !dismissed && status.mode === 'ALERT')
  const mood = status.mode === 'DISABLED'
    ? 'off'
    : isAlerting
      ? 'calm_alert'
      : status.mode === 'SCRIBE'
        ? 'writing'
        : status.mode === 'ACTIVE'
          ? 'attentive'
          : status.mode === 'INVESTIGATING'
            ? 'focused'
            : 'sleepy'

  return (
    <div className="relative flex h-full w-full flex-col justify-between overflow-hidden p-3 select-none">
      <Aurora />

      <StatusBar
        mode={status.mode}
        modeLabel={modeLabel}
        monitoring={status.monitoring}
        demo={status.demo}
        band={status.band}
        connection={connection}
        soundOn={soundOn}
        onToggleSound={toggleSound}
        onHide={hide}
        onWorkspace={openWorkspace}
      />

      <div className="my-auto flex flex-col items-center justify-center">
        <Mascot mood={mood} size={176} alert={isAlerting} />
      </div>

      <div className="relative z-10 w-full">
        <AnimatePresence mode="wait">
          {consentOpen ? (
            <ConsentCard
              key="consent"
              value={consentSource}
              onChange={setConsentSource}
              onStart={(src) => {
                start(src)
                closeConsent()
              }}
              onCancel={closeConsent}
              busy={busy}
            />
          ) : isAlerting && alert ? (
            <AlertCard
              key="alert"
              band={alert.payload.band ?? 'HOLD'}
              headline={alert.payload.headline ?? 'Verification Needed'}
              explanation={alert.payload.explanation}
              reasonCodes={alert.payload.reason_codes}
              evidenceIds={alert.payload.evidence_ids}
              actions={alert.payload.next_actions}
              demo={status.demo}
              onAction={handleAction}
              onCopy={copyRefusal}
              onDismiss={dismiss}
            />
          ) : status.mode === 'SCRIBE' ? (
            <ScribeCard
              key="scribe"
              draft={lastDraft}
              busy={busy}
              onDraft={(kind) => draft(kind)}
              onOpenWorkspace={openWorkspace}
            />
          ) : clipboard ? (
            <ClipboardCard
              key="clipboard"
              check={clipboard}
              onDismiss={() => null}
              onWorkspace={openWorkspace}
            />
          ) : (
            <StatusBubble
              key="status"
              mode={status.mode}
              modeLabel={modeLabel}
              monitoring={status.monitoring}
              sourceLabel={status.sourceLabel}
              demo={status.demo}
              band={status.band}
              connection={connection}
              busy={busy}
              onStart={() => openConsent()}
              onStop={stop}
              onDemo={() => demo('beneficiary_change')}
              onWorkspace={openWorkspace}
              onCheckClipboard={checkClipboard}
            />
          )}
        </AnimatePresence>
      </div>

      <Toast toast={toast} />
    </div>
  )
}
