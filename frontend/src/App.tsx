/**
 * Application shell for the Live Fact-Checker frontend.
 *
 * The frontend is a read-only observer of the backend pipeline. It starts and
 * stops sessions, streams the live transcript, and shows each claim's verdict as
 * it resolves. It never produces transcripts, claims or verdicts itself.
 *
 * There are two screens, not one long page.
 *
 * **Idle** shows the introduction in {@link EmptyState}: before any speech has
 * been processed there is nothing to report, and an empty workspace is the
 * worst possible thing to put in front of a first-time viewer.
 *
 * **Live** is ordered by how quickly a judge needs each thing:
 *
 *   1. the latest verdict, because it is the answer the product exists to give
 *   2. the pipeline, so the shape of the system reads alongside the answer
 *   3. the live transcript and the claim cards, which are the evidence for it
 *
 * Selecting a claim highlights the transcript line it came from; that single
 * piece of cross-linking is what makes the two columns read as one story.
 */

import { useCallback, useMemo, useState } from 'react'

import { ClaimPanel } from './components/ClaimPanel'
import { EmptyState } from './components/EmptyState'
import { ErrorPanel } from './components/ErrorPanel'
import { PipelineFlow } from './components/PipelineFlow'
import { SessionControls } from './components/SessionControls'
import { StatusBar } from './components/StatusBar'
import { TranscriptPanel } from './components/TranscriptPanel'
import { VerdictScoreboard } from './components/VerdictScoreboard'
import { useNow } from './hooks/useNow'
import { useSession } from './hooks/useSession'
import { BACKEND_URL } from './lib/config'
import { describeCard } from './lib/verdicts'

export default function App() {
  const {
    phase,
    connection,
    session,
    view,
    fault,
    start,
    stop,
    reconnect,
    dismissFault,
    clearErrors,
  } = useSession()

  const isLive = phase === 'active' || phase === 'stopping'
  const now = useNow(isLive)

  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null)
  const [isDemo, setIsDemo] = useState(false)

  // Resolve the selected claim to the transcript line it originated from, so
  // the transcript can scroll to and highlight it.
  const activeLineKey = useMemo(() => {
    if (selectedClaimId === null) return null
    const card = view.claims.find((claim) => claim.claimId === selectedClaimId)
    return card?.transcriptKey ?? null
  }, [selectedClaimId, view.claims])

  // The verdict of each checked line, so a transcript line can show the same
  // word and tone as the claim card it produced. Derived here from the claim
  // list rather than stored, so the reducer stays the only owner of state.
  const verdictsByClaimId = useMemo(() => {
    const map = new Map<string, ReturnType<typeof describeCard>>()
    for (const card of view.claims) map.set(card.claimId, describeCard(card))
    return map
  }, [view.claims])

  // Clicking a claim toggles it, so a second click returns to following the
  // live edge of the transcript.
  const handleSelect = useCallback((claimId: string) => {
    setSelectedClaimId((current) => (current === claimId ? null : claimId))
  }, [])

  const handleStart = useCallback(
    (options?: { demo?: boolean }) => {
      setSelectedClaimId(null)
      setIsDemo(options?.demo === true)
      void start(options)
    },
    [start],
  )

  const handleStop = useCallback(() => {
    setSelectedClaimId(null)
    setIsDemo(false)
    void stop()
  }, [stop])

  // The introduction owns the actions until there is a live session to control.
  // It stays up while the session is being created, so starting a run reads as
  // the button changing state rather than the page flashing an empty workspace.
  const showWorkspace = isLive

  return (
    <div className="app">
      <StatusBar
        phase={phase}
        connection={connection}
        backendUrl={BACKEND_URL}
        sessionId={session?.sessionId ?? null}
        connectedClients={session?.connectedClients ?? null}
        now={now}
        lastSpeechAt={view.lastSpeechAt}
        lastSpeaker={view.lastSpeaker}
        isDemo={isDemo}
      />

      <main className="app__main">
        <ErrorPanel
          fault={fault}
          errors={view.errors}
          onDismissFault={dismissFault}
          onClearErrors={clearErrors}
        />

        {!showWorkspace ? (
          <EmptyState
            onStartLive={() => handleStart({ demo: false })}
            onStartDemo={() => handleStart({ demo: true })}
            isStarting={phase === 'starting'}
            fault={null}
          />
        ) : (
          <>
            <VerdictScoreboard claims={view.claims} isLive={isLive} />

            <PipelineFlow view={view} isLive={isLive} now={now} />

            <SessionControls
              phase={phase}
              onStart={handleStart}
              onStop={handleStop}
              onReconnect={reconnect}
            />

            <div className="app__columns">
              <TranscriptPanel
                lines={view.transcripts}
                activeKey={activeLineKey}
                verdicts={verdictsByClaimId}
              />
              <ClaimPanel
                claims={view.claims}
                selectedClaimId={selectedClaimId}
                onSelect={handleSelect}
              />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
