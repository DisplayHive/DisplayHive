import type { TourDefinition } from '../types'
import { contentTypesTour } from './contentTypes'
import { layoutUsageTour } from './layoutUsage'
import { createEditContentTour } from './createEditContent'
import { screensTour } from './screens'
import { screengroupsTour } from './screengroups'
import { mediaTour } from './media'
import { dashboardTour } from './dashboard'

export const TOURS: TourDefinition[] = [
  dashboardTour,
  contentTypesTour,
  createEditContentTour,
  layoutUsageTour,
  screensTour,
  screengroupsTour,
  mediaTour,
]

export const toursByCategory = (category: TourDefinition['category']) =>
  TOURS.filter((tour) => tour.category === category)
