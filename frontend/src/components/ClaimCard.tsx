/**
 * A single claim and its verdict.
 *
 * The two states a judge cares about are visually unmistakable:
 *
 * - **pending** — animated, clearly "not an answer yet", never a grey verdict
 * - **resolved** — a colour-coded verdict band, the reason, and a real link to
 *   the source
 *
 * The card is a button so selecting it highlights the transcript line the claim
 * came from, which is what makes the two-column layout legible.
 */

import { displaySpeaker, formatClock, isLinkableSource, sourceDomain } from '../lib/format'
import { describeVerdict } from '../lib/verdicts'
import type { ClaimCard as ClaimCardModel } from '../types/model'

export interface ClaimCardProps {
  card: ClaimCardModel
  selected: boolean
  onSelect: (claimId: string) => void
}

export function ClaimCard({ card, selected, onSelect }: ClaimCardProps) {
  const verification = card.verification
  const descriptor = verification ? describeVerdict(verification.verdict) : null
  const tone = card.pending ? 'checking' : (descriptor?.tone ?? 'unknown')

  return (
    <li
      className={`card card--${tone}${selected ? ' card--selected' : ''}`}
      data-claim-id={card.claimId}
    >
      <button
        type="button"
        className="card__button"
        onClick={() => onSelect(card.claimId)}
        aria-pressed={selected}
      >
        <span className="card__head">
          <span className="card__speaker">{displaySpeaker(card.speaker)}</span>
          <span className="card__clock">{formatClock(card.timestamp)}</span>
          {card.claimType !== 'unspecified' && (
            <span className="card__type">{card.claimType.replace(/_/g, ' ')}</span>
          )}
          <span
            className={`verdict verdict--${tone}`}
            title={
              card.pending
                ? 'Evidence is being gathered for this claim.'
                : (descriptor?.description ?? '')
            }
          >
            {card.pending ? (
              <>
                <span className="verdict__spinner" aria-hidden="true" />
                CHECKING
              </>
            ) : (
              descriptor?.short
            )}
          </span>
        </span>

        <span className="card__claim">
          {card.claim !== '' ? card.claim : 'Claim text not seen by this client'}
        </span>
      </button>

      {verification !== null && (
        <div className="card__result">
          <p className="card__reason">{verification.reason}</p>
          <p className="card__source">
            <span className="card__sourceLabel">Source</span>
            {isLinkableSource(verification.source) ? (
              <a
                className="card__link"
                href={verification.source}
                target="_blank"
                rel="noreferrer noopener"
                title={verification.source}
              >
                {sourceDomain(verification.source)}
                <span className="card__external" aria-hidden="true">
                  ↗
                </span>
              </a>
            ) : (
              <span className="card__sourceText">{verification.source}</span>
            )}
          </p>
        </div>
      )}
    </li>
  )
}
