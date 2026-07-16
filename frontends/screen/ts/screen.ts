/**
 * Screen bundle entry point.
 */
import { consumeDdkFromFragment } from './screen/ddk';
import { screenInit } from './screen/index';

// Consume any dynamic device key from the URL fragment and scrub the URL
// before anything else runs.
consumeDdkFromFragment();

screenInit();
