import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import * as travelsApi from '../api/travels'
import { useAuth } from '../auth/AuthContext'
import { NotWiredNotice } from '../components/NotWiredNotice'
import type { ItineraryOption } from '../api/types'

export function TravelStatusPage() {
  const { travelId, kind, jobId } = useParams<{ travelId: string; kind: 'generation' | 'edit'; jobId: string }>()
  const { userId } = useAuth()
  const navigate = useNavigate()

  const statusQuery = useQuery({
    queryKey: ['travel-status', kind, jobId],
    queryFn: () => (kind === 'edit' ? travelsApi.getEditStatus(jobId!) : travelsApi.getGenerationStatus(jobId!)),
    enabled: !!jobId,
    // Generation runs in the background for minutes — poll until it settles.
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'done' || status === 'failed' ? false : 4000
    },
  })

  const [instruction, setInstruction] = useState('')
  const [editing, setEditing] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  async function handleEdit(e: FormEvent) {
    e.preventDefault()
    if (!travelId || !userId || !instruction.trim()) return
    setEditing(true)
    setEditError(null)
    try {
      const res = await travelsApi.editTravel(travelId, { requested_by: userId, changes: { instruction } })
      navigate(`/travels/${travelId}/status/edit/${res.job_id}`)
    } catch {
      setEditError('Failed to start the edit')
    } finally {
      setEditing(false)
    }
  }

  if (!travelId || !jobId) return null

  return (
    <div className="page">
      <h1>{kind === 'edit' ? 'Edit generation' : 'Itinerary generation'}</h1>
      <p>
        Travel <code>{travelId}</code>, job <code>{jobId}</code>
      </p>

      {statusQuery.isLoading && <p>Loading…</p>}
      {statusQuery.data && (
        <>
          <p>
            Status: <strong>{statusQuery.data.status}</strong>
            {statusQuery.data.status === 'processing' && ' — polling every 4s'}
          </p>
          {statusQuery.data.status === 'failed' && (
            <p className="error">{statusQuery.data.results[0]?.summary ?? 'Generation failed'}</p>
          )}
          {statusQuery.data.results.map((r) => (
            <ItineraryOptionCard key={r.version} option={r.option} />
          ))}

          {statusQuery.data.status === 'done' && (
            <section className="form-card">
              <h2>Request a change</h2>
              <form onSubmit={handleEdit}>
                <label>
                  What would you like to change?
                  <textarea
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="e.g. swap the Italian place on day 2 for Thai, make day 3 cheaper"
                    required
                  />
                </label>
                {editError && <p className="error">{editError}</p>}
                <button type="submit" disabled={editing}>
                  {editing ? 'Starting edit…' : 'Submit edit'}
                </button>
              </form>
            </section>
          )}
        </>
      )}
    </div>
  )
}

function ItineraryOptionCard({ option }: { option: ItineraryOption }) {
  const [vote, setVote] = useState<number | null>(null)
  const [comment, setComment] = useState('')

  return (
    <section className="card">
      <h2>Option {option.option_id}</h2>
      <p>{option.summary}</p>

      <h3>Flights</h3>
      <ul className="list">
        {option.flight_selections.map((f) => (
          <li key={f.group_id}>
            Group {f.group_id}: {f.airline_summary} — €{f.price_eur}
            {f.booking_url && (
              <>
                {' '}
                (<a href={f.booking_url} target="_blank" rel="noreferrer">
                  book
                </a>
                )
              </>
            )}
            {f.baggage_info && ` · baggage: ${f.baggage_info}`}
          </li>
        ))}
      </ul>

      <h3>Hotels</h3>
      <ul className="list">
        {option.hotel_selections.map((h) => (
          <li key={h.group_id}>
            Group {h.group_id}: {h.hotel_name}, {h.address} — €{h.price_eur}
            {h.booking_url && (
              <>
                {' '}
                (<a href={h.booking_url} target="_blank" rel="noreferrer">
                  book
                </a>
                )
              </>
            )}
          </li>
        ))}
      </ul>

      {option.days.map((day) => (
        <div key={day.day_number}>
          <h3>
            Day {day.day_number} — {day.date}
          </h3>
          <ul className="list">
            {day.items.map((item, i) => (
              <li key={i}>
                <strong>{item.time}</strong> [{item.type}] {item.title} — {item.location} ({item.duration_minutes} min,
                €{item.cost_eur})
                {item.notes && <div>{item.notes}</div>}
                {item.url && (
                  <div>
                    <a href={item.url} target="_blank" rel="noreferrer">
                      more info
                    </a>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      <h3>Price breakdown</h3>
      <ul className="list">
        {option.price_breakdown.map((p) => (
          <li key={p.group_id}>
            Group {p.group_id}: flights €{p.flights_cost}, hotel €{p.hotel_cost}, activities €{p.activities_cost},
            meals €{p.meals_cost}, local transport €{p.local_transport_cost} — total €{p.total_cost}{' '}
            {p.within_budget ? '(within budget)' : '(over budget)'}
          </li>
        ))}
      </ul>

      <p>{option.final_recommendation}</p>

      <NotWiredNotice>
        the <code>votes</code> table exists in <code>db/schema.sql</code> but no service exposes it — this vote and
        comment are UI-only and aren't sent anywhere. There's also no endpoint to mark an option as the group's
        selected itinerary.
      </NotWiredNotice>
      <div className="actions">
        <button type="button" onClick={() => setVote(1)} className={vote === 1 ? 'active' : ''}>
          👍 {vote === 1 ? '(voted)' : ''}
        </button>
        <button type="button" onClick={() => setVote(-1)} className={vote === -1 ? 'active' : ''}>
          👎 {vote === -1 ? '(voted)' : ''}
        </button>
      </div>
      <label>
        Comment (not sent anywhere)
        <input value={comment} onChange={(e) => setComment(e.target.value)} />
      </label>
    </section>
  )
}
