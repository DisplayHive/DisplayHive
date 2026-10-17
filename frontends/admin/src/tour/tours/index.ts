import type { TourDefinition } from '../types'
import { pluginRegistry } from '../../plugins/registry'
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
import { pluginsTour } from './plugins'

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
  pluginsTour,
]

/** The tours of the host and of the plugins that are switched on. */
export const allTours = (): TourDefinition[] => [...TOURS, ...pluginRegistry.tours.values()]

export const toursByCategory = (category: TourDefinition['category']) =>
  allTours().filter((tour) => tour.category === category)
