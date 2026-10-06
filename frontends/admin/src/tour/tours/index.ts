import type { TourDefinition } from '../types'
import { contentTypesTour } from './contentTypes'
import { layoutUsageTour } from './layoutUsage'
import { createEditContentTour } from './createEditContent'
import { screensTour } from './screens'
import { screengroupsTour } from './screengroups'
import { mediaTour } from './media'
import { dashboardTour } from './dashboard'
import { settingsTour } from './settings'
import { designsTour } from './designs'
import { devicesTour } from './devices'
import { usersTour } from './users'
import { importExportTour } from './importexport'
import { alertingTour } from './alerting'
import { pretalxTour } from './pretalx'

export const TOURS: TourDefinition[] = [
  dashboardTour,
  contentTypesTour,
  createEditContentTour,
  layoutUsageTour,
  screensTour,
  screengroupsTour,
  mediaTour,
  settingsTour,
  designsTour,
  devicesTour,
  usersTour,
  importExportTour,
  alertingTour,
  pretalxTour,
]

export const toursByCategory = (category: TourDefinition['category']) =>
  TOURS.filter((tour) => tour.category === category)
