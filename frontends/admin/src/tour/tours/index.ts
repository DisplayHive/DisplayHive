import type { TourDefinition } from '../types'
import { contentTypesTour } from './contentTypes'
import { layoutUsageTour } from './layoutUsage'
import { createEditContentTour } from './createEditContent'

export const TOURS: TourDefinition[] = [contentTypesTour, createEditContentTour, layoutUsageTour]

export const toursByCategory = (category: TourDefinition['category']) =>
  TOURS.filter((tour) => tour.category === category)
