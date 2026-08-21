import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { NotWiredNotice } from '../components/NotWiredNotice'
import * as travelsApi from '../api/travels'
import * as searchApi from '../api/search'
import { nightsBetween } from '../lib/dates'
import { ApiError } from '../lib/apiClient'
import type { FlightOffer, HotelOffer } from '../api/types'

type Step = 'basics' | 'subgroups' | 'flights' | 'hotels' | 'review'

interface Subgroup {
  groupId: number
  adults: number
  children: number
  childrenAges: number[]
  budgetMax: string
  wheelchairAccessible: boolean
  preferences: string
}

function newSubgroup(groupId: number): Subgroup {
  return { groupId, adults: 1, children: 0, childrenAges: [], budgetMax: '', wheelchairAccessible: false, preferences: '' }
}

export function TripPlanningPage() {
  const { groupId: travelGroupId } = useParams<{ groupId: string }>()
  const { userId } = useAuth()
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>('basics')

  // --- trip basics ---
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [destinationCityId, setDestinationCityId] = useState('')
  const [originCityName, setOriginCityName] = useState('')
  const [destinationCityName, setDestinationCityName] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [dateRangeDays, setDateRangeDays] = useState(2)
  const [userPreferences, setUserPreferences] = useState('')
  const [travelPace, setTravelPace] = useState('moderate')

  // --- subgroups: each is one booking unit — one shared flight, one shared
  // hotel room (or set of rooms), never split across two bookings. ---
  const [subgroups, setSubgroups] = useState<Subgroup[]>([newSubgroup(1)])
  const [nextGroupId, setNextGroupId] = useState(2)

  // --- flight/hotel search + selection ---
  const [flightOffers, setFlightOffers] = useState<FlightOffer[]>([])
  const [selectedFlights, setSelectedFlights] = useState<Record<number, FlightOffer>>({})
  const [hotelOffers, setHotelOffers] = useState<HotelOffer[]>([])
  const [selectedHotels, setSelectedHotels] = useState<Record<number, HotelOffer>>({})

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function updateSubgroup(groupId: number, patch: Partial<Subgroup>) {
    setSubgroups((groups) => groups.map((g) => (g.groupId === groupId ? { ...g, ...patch } : g)))
  }

  function setChildrenCount(groupId: number, count: number) {
    setSubgroups((groups) =>
      groups.map((g) => {
        if (g.groupId !== groupId) return g
        const ages = [...g.childrenAges]
        ages.length = count
        return { ...g, children: count, childrenAges: ages.map((a) => a ?? 0) }
      }),
    )
  }

  function addSubgroup() {
    setSubgroups((groups) => [...groups, newSubgroup(nextGroupId)])
    setNextGroupId((n) => n + 1)
  }

  function removeSubgroup(groupId: number) {
    setSubgroups((groups) => groups.filter((g) => g.groupId !== groupId))
  }

  function baseGroupInputs() {
    return subgroups.map((s) => ({
      group_id: s.groupId,
      adults: s.adults,
      children: s.children,
      children_ages: s.childrenAges,
      budget_max: s.budgetMax ? Number(s.budgetMax) : null,
      wheelchair_accessible: s.wheelchairAccessible,
      preferences: s.preferences,
    }))
  }

  async function handleSearchFlights() {
    setLoading(true)
    setError(null)
    try {
      const res = await searchApi.searchFlights({
        origin_city: originCityName,
        destination_city: destinationCityName,
        base_departure_date: startDate,
        trip_length_nights: nightsBetween(startDate, endDate),
        date_range_days: dateRangeDays,
        top_n_outbound: 1,
        groups: baseGroupInputs(),
      })
      setFlightOffers(res.offers)
      setStep('flights')
    } catch {
      setError('Flight search failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleSearchHotels() {
    setLoading(true)
    setError(null)
    try {
      const pairs = new Map<string, [string, string]>()
      for (const offer of Object.values(selectedFlights)) {
        pairs.set(`${offer.outbound_date}|${offer.return_date}`, [offer.outbound_date, offer.return_date])
      }
      const res = await searchApi.searchHotels({
        location: destinationCityName || undefined,
        stay_date_ranges: Array.from(pairs.values()),
        groups: baseGroupInputs(),
      })
      setHotelOffers(res.offers)
      setStep('hotels')
    } catch {
      setError('Hotel search failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit() {
    if (!travelGroupId || !userId) return
    setLoading(true)
    setError(null)
    try {
      const res = await travelsApi.createTravel({
        group_id: travelGroupId,
        created_by: userId,
        title,
        description: description || null,
        destination_city_id: destinationCityId,
        start_date: startDate,
        end_date: endDate,
        groups: subgroups.map((s) => ({
          group_id: s.groupId,
          adults: s.adults,
          children: s.children,
          budget_max: s.budgetMax ? Number(s.budgetMax) : null,
          wheelchair_accessible: s.wheelchairAccessible,
          preferences: s.preferences,
        })),
        user_preferences: userPreferences,
        travel_pace: travelPace,
        flight_offers: subgroups.map((s) => selectedFlights[s.groupId]).filter(Boolean),
        hotel_offers: subgroups.map((s) => selectedHotels[s.groupId]).filter(Boolean),
      })
      navigate(`/travels/${res.travelId}/status/generation/${res.jobId}`)
    } catch (err) {
      setError(err instanceof ApiError ? `Failed to create travel (${err.status})` : 'Failed to create travel')
    } finally {
      setLoading(false)
    }
  }

  const allFlightsSelected = subgroups.every((s) => selectedFlights[s.groupId])
  const allHotelsSelected = subgroups.every((s) => selectedHotels[s.groupId])

  return (
    <div className="page">
      <h1>Plan a new travel</h1>
      <p className="steps">
        {(['basics', 'subgroups', 'flights', 'hotels', 'review'] as Step[]).map((s) => (
          <span key={s} className={s === step ? 'step active' : 'step'}>
            {s}
          </span>
        ))}
      </p>
      {error && <p className="error">{error}</p>}

      {step === 'basics' && (
        <section className="form-card">
          <h2>Trip basics</h2>
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>
          <label>
            Description
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>

          <NotWiredNotice>
            no <code>/cities</code> lookup endpoint exists yet, so the destination must be entered twice: as a raw{' '}
            <code>cities.id</code> UUID (for <code>POST /travels</code>) and as a free-text city name (for
            search-service, which only knows city names, not UUIDs).
          </NotWiredNotice>
          <label>
            Destination city ID (uuid, for the travel record)
            <input value={destinationCityId} onChange={(e) => setDestinationCityId(e.target.value)} required placeholder="00000000-0000-0000-0000-000000000000" />
          </label>
          <label>
            Origin city (free text, for flight/hotel search — e.g. "Paris")
            <input value={originCityName} onChange={(e) => setOriginCityName(e.target.value)} required />
          </label>
          <label>
            Destination city (free text, for flight/hotel search — e.g. "Berlin")
            <input value={destinationCityName} onChange={(e) => setDestinationCityName(e.target.value)} required />
          </label>

          <label>
            Start date
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </label>
          <label>
            End date
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
          </label>
          <label>
            Flexible by ± days (how far around the start date to search for cheaper flights)
            <input type="number" min={0} value={dateRangeDays} onChange={(e) => setDateRangeDays(Number(e.target.value))} />
          </label>
          <label>
            Travel pace
            <select value={travelPace} onChange={(e) => setTravelPace(e.target.value)}>
              <option value="relaxed">relaxed</option>
              <option value="moderate">moderate</option>
              <option value="packed">packed</option>
            </select>
          </label>
          <label>
            Preferences (free text — food, interests, must-see places)
            <textarea value={userPreferences} onChange={(e) => setUserPreferences(e.target.value)} />
          </label>

          <button
            type="button"
            disabled={!title || !destinationCityId || !originCityName || !destinationCityName || !startDate || !endDate}
            onClick={() => setStep('subgroups')}
          >
            Next: subgroups
          </button>
        </section>
      )}

      {step === 'subgroups' && (
        <section>
          <h2>Subgroups</h2>
          <p>
            Each subgroup is one booking unit: everyone in it shares the same flight and the same hotel room(s) —
            a subgroup can book multiple rooms, but it's never split across two different flights or hotels.
          </p>
          {subgroups.map((sg) => (
            <div className="card" key={sg.groupId}>
              <h3>Subgroup {sg.groupId}</h3>
              <label>
                Adults
                <input type="number" min={1} value={sg.adults} onChange={(e) => updateSubgroup(sg.groupId, { adults: Number(e.target.value) })} />
              </label>
              <label>
                Children
                <input type="number" min={0} value={sg.children} onChange={(e) => setChildrenCount(sg.groupId, Number(e.target.value))} />
              </label>
              {sg.childrenAges.map((age, i) => (
                <label key={i}>
                  Child {i + 1} age
                  <input
                    type="number"
                    min={0}
                    max={17}
                    value={age}
                    onChange={(e) => {
                      const ages = [...sg.childrenAges]
                      ages[i] = Number(e.target.value)
                      updateSubgroup(sg.groupId, { childrenAges: ages })
                    }}
                  />
                </label>
              ))}
              <label>
                Budget max, EUR total (optional — covers flights + hotel + activities + food + local transport for this subgroup)
                <input type="number" value={sg.budgetMax} onChange={(e) => updateSubgroup(sg.groupId, { budgetMax: e.target.value })} />
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={sg.wheelchairAccessible}
                  onChange={(e) => updateSubgroup(sg.groupId, { wheelchairAccessible: e.target.checked })}
                />
                Wheelchair accessible needed (accessibility only — not medical/dietary)
              </label>
              <label>
                Preferences (free text — this subgroup's own food/interest preferences)
                <textarea value={sg.preferences} onChange={(e) => updateSubgroup(sg.groupId, { preferences: e.target.value })} />
              </label>
              {subgroups.length > 1 && (
                <button type="button" onClick={() => removeSubgroup(sg.groupId)}>
                  Remove subgroup
                </button>
              )}
            </div>
          ))}
          <div className="actions">
            <button type="button" onClick={addSubgroup}>
              + Add subgroup (members addable later)
            </button>
          </div>
          <div className="actions">
            <button type="button" onClick={() => setStep('basics')}>
              Back
            </button>
            <button type="button" disabled={loading} onClick={handleSearchFlights}>
              {loading ? 'Searching flights…' : 'Search flights'}
            </button>
          </div>
        </section>
      )}

      {step === 'flights' && (
        <section>
          <h2>Select a flight per subgroup</h2>
          {subgroups.map((sg) => {
            const offers = flightOffers.filter((o) => o.group_id === sg.groupId)
            return (
              <div className="card" key={sg.groupId}>
                <h3>Subgroup {sg.groupId}</h3>
                {offers.length === 0 && <p>No flight offers found for this subgroup.</p>}
                <ul className="list">
                  {offers.map((offer, i) => (
                    <li key={i}>
                      <label>
                        <input
                          type="radio"
                          name={`flight-${sg.groupId}`}
                          checked={selectedFlights[sg.groupId] === offer}
                          onChange={() => setSelectedFlights((sel) => ({ ...sel, [sg.groupId]: offer }))}
                        />
                        {offer.outbound_date} → {offer.return_date} · {offer.price ?? '?'} {offer.currency} · {offer.status}
                        {offer.note && ` — ${offer.note}`}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
          <div className="actions">
            <button type="button" onClick={() => setStep('subgroups')}>
              Back
            </button>
            <button type="button" disabled={!allFlightsSelected || loading} onClick={handleSearchHotels}>
              {loading ? 'Searching hotels…' : 'Search hotels'}
            </button>
          </div>
        </section>
      )}

      {step === 'hotels' && (
        <section>
          <h2>Select a hotel per subgroup</h2>
          {subgroups.map((sg) => {
            const offers = hotelOffers.filter((o) => o.group_id === sg.groupId)
            return (
              <div className="card" key={sg.groupId}>
                <h3>Subgroup {sg.groupId}</h3>
                {offers.length === 0 && <p>No hotel offers found for this subgroup.</p>}
                <ul className="list">
                  {offers.map((offer, i) => (
                    <li key={i}>
                      <label>
                        <input
                          type="radio"
                          name={`hotel-${sg.groupId}`}
                          checked={selectedHotels[sg.groupId] === offer}
                          onChange={() => setSelectedHotels((sel) => ({ ...sel, [sg.groupId]: offer }))}
                        />
                        {offer.property_name} · {offer.total_price ?? '?'} {offer.currency} · {offer.status}
                        {offer.note && ` — ${offer.note}`}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
          <div className="actions">
            <button type="button" onClick={() => setStep('flights')}>
              Back
            </button>
            <button type="button" disabled={!allHotelsSelected} onClick={() => setStep('review')}>
              Review
            </button>
          </div>
        </section>
      )}

      {step === 'review' && (
        <section>
          <h2>Review</h2>
          <div className="card">
            <p>
              <strong>{title}</strong> — {startDate} to {endDate} ({travelPace})
            </p>
            {subgroups.map((sg) => (
              <p key={sg.groupId}>
                Subgroup {sg.groupId}: {sg.adults} adults, {sg.children} children — flight{' '}
                {selectedFlights[sg.groupId]?.price ?? '?'} {selectedFlights[sg.groupId]?.currency}, hotel{' '}
                {selectedHotels[sg.groupId]?.total_price ?? '?'} {selectedHotels[sg.groupId]?.currency}
              </p>
            ))}
          </div>
          <div className="actions">
            <button type="button" onClick={() => setStep('hotels')}>
              Back
            </button>
            <button type="button" disabled={loading} onClick={handleSubmit}>
              {loading ? 'Starting generation…' : 'Generate itinerary'}
            </button>
          </div>
        </section>
      )}
    </div>
  )
}
