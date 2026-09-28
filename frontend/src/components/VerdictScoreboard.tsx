/**
 * Verdict scoreboard.
 *
 * A judge's one-second read: how many claims were checked, and how they broke
 * down. The most recent verdict is enlarged because during a live debate that
 * is the number people actually want.
 *
 * `UNVERIFIABLE` is presented as its own outcome rather than folded into a
 * pass or a fail, which matches the verification module's principle that
 * missing evidence is never a confirmation.
 */

import { formatClock, tallyVerdicts } from '../lib/format'
import { describeVerdict } from '../lib/verdicts'
import type { ClaimCard } from '../types/model'

export interface VerdictScoreboardProps {
  claims: ClaimCard[]
}

export function VerdictScoreboard({ claims }: VerdictScoreboardProps) {
  const tally = tallyVerdicts(claims)
  const checked = tally.true + tally.false + tally.unverifiable
  const pending = claims.length - checked

  const resolved = claims.filter((card) => card.verification !== null)
  const latest = resolved[resolved.length - 1]
  const latestVerdict = latest?.verification ?? null
  const latestDescriptor = latestVerdict ? describeVerdict(latestVerdict.verdict) : null

  return (
    <section className="scoreboard" aria-label="Verdict summary">
      <div className="scoreboard__head">
        <h2 className="scoreboard__title">Fact-check summary</h2>
        {claims.length === 0 ? (
          <span className="scoreboard__idle">No claims yet</span>
        ) : (
          <span className="scoreboard__total">
            <strong>{checked}</strong> checked
            {pending > 0 && <> · {pending} in flight</>}
          </span>
        )}
      </div>

      {latestDescriptor !== null && latestVerdict !== null && (
        <div className={`scoreboard__hero scoreboard__hero--${latestDescriptor.tone}`}>
          <span className="scoreboard__heroVerdict">{latestDescriptor.short}</span>
          <span className="scoreboard__heroBody">
            <span className="scoreboard__heroClaim">{latest?.claim || latestVerdict.reason}</span>
            <span className="scoreboard__heroMeta">
              {latestVerdict.reason}
              {latest !== undefined && <> · {formatClock(latest.timestamp)}</>}
            </span>
          </span>
        </div>
      )}

      <dl className="scoreboard__stats">
        <div className="scoreboard__stat scoreboard__stat--supported">
          <dt>True</dt>
          <dd>{tally.true}</dd>
        </div>
        <div className="scoreboard__stat scoreboard__stat--refuted">
          <dt>False</dt>
          <dd>{tally.false}</dd>
        </div>
        <div className="scoreboard__stat scoreboard__stat--unknown">
          <dt>Unverifiable</dt>
          <dd>{tally.unverifiable}</dd>
        </div>
        <div className="scoreboard__stat scoreboard__stat--pending">
          <dt>Checking</dt>
          <dd>{pending}</dd>
        </div>
      </dl>
    </section>
  )
}
