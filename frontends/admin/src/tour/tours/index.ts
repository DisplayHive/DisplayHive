import type { TourDefinition } from '../types'
import { contentTypesTour } from './contentTypes'
import { layoutUsageTour } from './layoutUsage'

export const TOURS: TourDefinition[] = [contentTypesTour, layoutUsageTour]

export const toursByCategory = (category: TourDefinition['category']) =>
  TOURS.filter((tour) => tour.category === category)
