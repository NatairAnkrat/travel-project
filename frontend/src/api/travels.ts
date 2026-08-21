import { travelApi } from '../lib/apiClient'
import type { CreateTravelRequest, CreateTravelResponse, EditCreatedResponse, EditRequest, GenerationStatus } from './types'

export function createTravel(req: CreateTravelRequest): Promise<CreateTravelResponse> {
  return travelApi('/api/v1/travels', { method: 'POST', body: req })
}

export function getGenerationStatus(jobId: string): Promise<GenerationStatus> {
  return travelApi(`/api/v1/travels/generation/${jobId}`)
}

export function editTravel(travelId: string, req: EditRequest): Promise<EditCreatedResponse> {
  return travelApi(`/api/v1/travels/${travelId}/edit`, { method: 'POST', body: req })
}

export function getEditStatus(jobId: string): Promise<GenerationStatus> {
  return travelApi(`/api/v1/edits/${jobId}`)
}
