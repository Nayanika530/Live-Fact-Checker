/**
 * Live transcript.
 *
 * Three behaviours matter for reading a live debate:
 *
 * 1. **Interim segments** arrive with `isFinal: false` and are revised in place
 *    by the reducer, so a growing line is rendered dimmed and italic to make it
 *    obvious the recogniser is still working on it. Only a finalized line is
 *    claim-checked by the backend.
 * 2. **Claimed lines** are marked, so a judge can see which sentences produced
 *    a verdict.
 * 3. **Selecting a claim** scrolls its originating line into view and holds it
 *    highlighted, which is what ties the two columns together.
 */

import { useEffect, useRef } from 'react'

import { displaySpeaker, formatClock, speakerIndex, speakerInitials } from '../lib/format'
import type { TranscriptLine } from '../types/model'

export interface TranscriptPanelProps {
  lines: TranscriptLine[]
  /** Key of the line to highlight, usually the selected claim's origin. */
  activeKey: string | null
}

export function TranscriptPanel({ lines, activeKey }: TranscriptPanelProps) {
  const endRef = useRef<HTMLDivElement | null>(null)
  const activeRef = useRef<HTMLLIElement | null>(null)

  // Speaker colours are assigned by order of first appearance, so Speaker 1 is
  // always the same colour within a session.
  const speakerOrder: string[] = []
  for (const line of lines) {
    const label = displaySpeaker(line.speaker)
    if (!speakerOrder.includes(label)) speakerOrder.push(label)
  }

  // Follow the live edge, unless a claim selection has taken priority.
  useEffect(() => {
    if (activeKey !== null) {
      activeRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      return
    }
    endRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [lines.length, activeKey])

  return (
    <section className="panel panel--transcript" aria-label="Live transcript">
      <h2 className="panel__title">
        Live transcript
        {lines.length > 0 && (
          <span className="panel__count">{lines.length} segments</span>
        )}
      </h2>

      {lines.length === 0 ? (
        <p className="empty">
          Waiting for speech. Start a session and have the microphone module post a
          transcript, or press <strong>Run demo</strong> to replay the scripted
          pipeline.
        </p>
      ) : (
        <ol className="transcript">
          {lines.map((line) => {
            const isActive = line.key === activeKey

            return (
              <li
                key={line.key}
                ref={isActive ? activeRef : undefined}
                className={[
                  'line',
                  line.isFinal ? 'line--final' : 'line--interim',
                  line.claimId !== null ? 'line--claimed' : '',
                  isActive ? 'line--active' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                data-claim-id={line.claimId ?? undefined}
              >
                <span
                  className="line__avatar"
                  data-tone={speakerIndex(line.speaker, speakerOrder)}
                  aria-hidden="true"
                >
                  {speakerInitials(line.speaker)}
                </span>
                <span className="line__meta">
                  <span className="line__clock">{formatClock(line.timestamp)}</span>
                  <span className="line__speaker">{displaySpeaker(line.speaker)}</span>
                </span>
                <span className="line__text">{line.text}</span>
                {line.claimId !== null && (
                  <span className="line__flag" title={`Checked as ${line.claimId}`}>
                    ✓ checked
                  </span>
                )}
              </li>
            )
          })}
          <div ref={endRef} />
        </ol>
      )}
    </section>
  )
}
